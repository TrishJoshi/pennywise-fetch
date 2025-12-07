from sqlalchemy.orm import Session
from app.schemas import PennyWiseBackup
from app.models import (
    Transaction, Category, Card, AccountBalance, Subscription,
    MerchantMapping, UnrecognizedSms, ChatMessage, TransactionRule,
    RuleApplication, ExchangeRate, ImportLog, ImportRowLog, Bucket
)
from decimal import Decimal
from datetime import datetime
import logging
from sqlalchemy import inspect

logger = logging.getLogger(__name__)

def process_backup(backup_data: PennyWiseBackup, db: Session, filename: str):
    # Create Import Log
    import_log = ImportLog(filename=filename, status="STARTED")
    db.add(import_log)
    db.commit()
    db.refresh(import_log)

    try:
        if not backup_data.database:
            logger.warning("No database snapshot found in backup.")
            import_log.status = "COMPLETED"
            import_log.completed_at = datetime.utcnow()
            db.commit()
            return

        snapshot = backup_data.database
        
        # Process each entity type
        process_entity_group(db, import_log, Category, snapshot.categories, ['name'], 'category_id')
        process_entity_group(db, import_log, Card, snapshot.cards, ['id'], 'card_id')
        
        # Special handling for Transactions to support Soft Deletes
        transaction_ids_in_backup = set()
        if snapshot.transactions:
            transaction_ids_in_backup = {t.transaction_hash for t in snapshot.transactions if t.transaction_hash}
            process_entity_group(db, import_log, Transaction, snapshot.transactions, ['transaction_hash'], 'transaction_id')
        
        # Soft Delete Logic for Transactions
        # Find transactions in DB that are NOT in backup (and not already deleted)
        # We assume 'transaction_hash' is the unique identifier from source
        existing_transactions = db.query(Transaction).filter(Transaction.is_deleted == False).all()
        for txn in existing_transactions:
            if txn.transaction_hash and txn.transaction_hash not in transaction_ids_in_backup:
                # Mark as deleted
                txn.is_deleted = True
                
                # Revert balance from Bucket
                if txn.amount and txn.category and txn.transaction_type in ['EXPENSE', 'INCOME']:
                    cat = db.query(Category).filter(Category.name == txn.category).first()
                    if cat and cat.bucket:
                        bucket = cat.bucket
                        if txn.transaction_type == 'EXPENSE':
                            bucket.total_amount = (bucket.total_amount or 0) + txn.amount
                        elif txn.transaction_type == 'INCOME':
                            bucket.total_amount = (bucket.total_amount or 0) - txn.amount
                        db.add(bucket)
                
                db.add(txn)
                
                # Log deletion
                row_log = ImportRowLog(
                    import_log_id=import_log.id,
                    action="DELETED",
                    table_name=Transaction.__tablename__,
                    transaction_id=txn.id
                )
                db.add(row_log)

        process_entity_group(db, import_log, AccountBalance, snapshot.account_balances, ['bank_name', 'account_last4', 'timestamp'], 'account_balance_id')
        process_entity_group(db, import_log, Subscription, snapshot.subscriptions, ['id'], 'subscription_id')
        process_entity_group(db, import_log, MerchantMapping, snapshot.merchant_mappings, ['merchant_name'], 'merchant_mapping_id')
        process_entity_group(db, import_log, UnrecognizedSms, snapshot.unrecognized_sms, ['sender', 'sms_body'], 'unrecognized_sms_id')
        process_entity_group(db, import_log, ChatMessage, snapshot.chat_messages, ['id'], 'chat_message_id')
        process_entity_group(db, import_log, TransactionRule, snapshot.transaction_rules, ['id'], 'transaction_rule_id')
        process_entity_group(db, import_log, RuleApplication, snapshot.rule_applications, ['id'], 'rule_application_id')
        process_entity_group(db, import_log, ExchangeRate, snapshot.exchange_rates, ['from_currency', 'to_currency'], 'exchange_rate_id')

        import_log.status = "COMPLETED"
        import_log.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        logger.error(f"Import failed: {e}")
        db.rollback()
        try:
            log_entry = db.query(ImportLog).filter(ImportLog.id == import_log.id).first()
            if log_entry:
                log_entry.status = "FAILED"
                log_entry.error_message = str(e)
                log_entry.completed_at = datetime.utcnow()
                db.commit()
        except Exception as inner_e:
            logger.error(f"Failed to update import log status: {inner_e}")
        raise e

def process_entity_group(db: Session, import_log: ImportLog, model, data_list, unique_keys, fk_field_name):
    if not data_list:
        return

    for item in data_list:
        item_data = item.dict(exclude_unset=True)
        
        filters = {k: item_data.get(k) for k in unique_keys}
        if any(v is None for v in filters.values()):
            continue

        existing = db.query(model).filter_by(**filters).first()
        
        action = "SKIPPED"
        entity_id = None

        if existing:
            # Update
            changed = False
            
            # Capture old values for Transaction logic
            old_amount = getattr(existing, 'amount', None)
            old_category_name = getattr(existing, 'category', None)
            old_type = getattr(existing, 'transaction_type', None)
            
            for k, v in item_data.items():
                if hasattr(existing, k) and getattr(existing, k) != v:
                    setattr(existing, k, v)
                    changed = True
            
            if changed:
                action = "UPDATED"
                db.flush()
            else:
                action = "SKIPPED"
            
            pk_col = list(model.__table__.primary_key.columns)[0].name
            entity_id = getattr(existing, pk_col)
            
            # Handle Transaction Updates
            if model == Transaction and action == "UPDATED":
                # Revert old effect
                if old_amount and old_category_name and old_type in ['EXPENSE', 'INCOME']:
                    old_cat = db.query(Category).filter(Category.name == old_category_name).first()
                    if old_cat and old_cat.bucket:
                        old_bucket = old_cat.bucket
                        if old_type == 'EXPENSE':
                            old_bucket.total_amount = (old_bucket.total_amount or 0) + old_amount
                        elif old_type == 'INCOME':
                            old_bucket.total_amount = (old_bucket.total_amount or 0) - old_amount
                        db.add(old_bucket)
                
                # Apply new effect (handled below in shared block)

        else:
            # Insert
            new_obj = model(**item_data)
            db.add(new_obj)
            db.flush()
            action = "ADDED"
            
            pk_col = list(model.__table__.primary_key.columns)[0].name
            entity_id = getattr(new_obj, pk_col)

        # Handle Category Creation - Ensure Bucket Exists
        if model == Category and action == "ADDED":
            # Create a Bucket for this category if not linked
            # Since it's new, it won't have a bucket_id unless we set it.
            # We create a 1-to-1 bucket mapping initially.
            new_bucket = Bucket(name=item_data.get('name'))
            db.add(new_bucket)
            db.flush()
            
            # Link category to bucket
            # We need to fetch the category object again or use new_obj
            if 'new_obj' in locals():
                new_obj.bucket_id = new_bucket.id
            elif 'existing' in locals():
                existing.bucket_id = new_bucket.id # Should not happen for ADDED but safety
            
            db.flush()

        # Handle Transaction Expense/Income Logic (Shared for ADDED and UPDATED)
        if model == Transaction and action in ["ADDED", "UPDATED"]:
            t_amount = item_data.get('amount')
            t_category_name = item_data.get('category')
            t_type = item_data.get('transaction_type')
            
            if t_amount and t_category_name and t_type in ['EXPENSE', 'INCOME']:
                cat = db.query(Category).filter(Category.name == t_category_name).first()
                
                # If category doesn't exist (should have been imported first, but safety check)
                if not cat:
                    # Create category and bucket on the fly? 
                    # Better to assume categories are processed first.
                    pass
                elif cat:
                    # Ensure category has a bucket
                    if not cat.bucket:
                        # Create bucket if missing
                        bucket = Bucket(name=cat.name)
                        db.add(bucket)
                        db.flush()
                        cat.bucket_id = bucket.id
                        db.add(cat)
                        db.flush()
                    
                    bucket = cat.bucket
                    
                    if t_type == 'EXPENSE':
                        bucket.total_amount = (bucket.total_amount or 0) - Decimal(t_amount)
                    elif t_type == 'INCOME':
                        bucket.total_amount = (bucket.total_amount or 0) + Decimal(t_amount)
                    
                    db.add(bucket)

        # Log the row change
        row_log = ImportRowLog(
            import_log_id=import_log.id,
            action=action,
            table_name=model.__tablename__,
        )
        setattr(row_log, fk_field_name, entity_id)
        db.add(row_log)
