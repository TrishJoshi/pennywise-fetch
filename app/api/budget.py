from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Category, Transaction, Bucket, DistributionEvent, DistributionLog
from app.schemas import (
    CategoryEntity, 
    BudgetUpdate, 
    FundTransfer, 
    DistributeIncomeRequest, 
    TransactionEntity,
    DistributionEventEntity,
    BucketEntity
)
from decimal import Decimal
from typing import List
from sqlalchemy import desc

router = APIRouter(
    prefix="/budget",
    tags=["budget"],
    responses={404: {"description": "Not found"}},
)

@router.get("/buckets", response_model=List[BucketEntity])
def get_buckets(db: Session = Depends(get_db)):
    # Return all buckets with nested categories
    return db.query(Bucket).order_by(Bucket.name).all()

@router.get("/income-transactions", response_model=List[TransactionEntity])
def get_income_transactions(db: Session = Depends(get_db)):
    # Fetch recent income transactions (limit 20 for now)
    return db.query(Transaction).filter(
        Transaction.category == "Income",
        Transaction.transaction_type == "INCOME"
    ).order_by(desc(Transaction.date_time)).limit(20).all()

@router.get("/distributions", response_model=List[DistributionEventEntity])
def get_distributions(db: Session = Depends(get_db)):
    events = db.query(DistributionEvent).order_by(desc(DistributionEvent.timestamp)).limit(50).all()
    # Map to entity manually to handle nested logs
    result = []
    for event in events:
        logs = []
        for log in event.logs:
            logs.append({
                "id": log.id,
                "bucketName": log.bucket.name if log.bucket else "Unknown",
                "amount": log.amount
            })
        result.append({
            "id": event.id,
            "transactionId": event.transaction_id,
            "timestamp": event.timestamp,
            "totalAmount": event.total_amount,
            "isReverted": event.is_reverted,
            "logs": logs
        })
    return result

@router.put("/buckets/{bucket_id}", response_model=BucketEntity)
def update_bucket_budget(bucket_id: int, budget: BudgetUpdate, db: Session = Depends(get_db)):
    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")
    
    bucket.monthly_amount = Decimal(budget.monthly_amount)
    db.commit()
    db.refresh(bucket)
    return bucket

@router.delete("/buckets/{bucket_id}")
def delete_bucket(bucket_id: int, db: Session = Depends(get_db)):
    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")
    
    if bucket.categories:
        raise HTTPException(status_code=400, detail="Cannot delete bucket with associated categories. Move categories first.")
        
    if bucket.total_amount != 0:
        raise HTTPException(status_code=400, detail="Cannot delete bucket with non-zero balance. Transfer funds first.")

    try:
        db.delete(bucket)
        db.commit()
        return {"message": "Bucket deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/categories/{category_id}/bucket")
def move_category_to_bucket(category_id: int, bucket_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Target bucket not found")
        
    category.bucket_id = bucket.id
    db.commit()
    return {"message": "Category moved successfully"}

@router.post("/distribute")
def distribute_income(request: DistributeIncomeRequest, db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == request.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction.category != "Income" or transaction.transaction_type != "INCOME":
        raise HTTPException(status_code=400, detail="Transaction must be of category 'Income' and type 'INCOME'")
    
    buckets = db.query(Bucket).all()
    others_bucket = next((b for b in buckets if b.name == "Others"), None)
    
    if not others_bucket:
        # Create Others bucket if it doesn't exist
        others_bucket = Bucket(name="Others")
        db.add(others_bucket)
        db.flush()
        buckets.append(others_bucket)

    total_needed = sum((b.monthly_amount or Decimal(0)) for b in buckets if b.name != "Others")
    
    if transaction.amount < total_needed:
        raise HTTPException(status_code=400, detail=f"Insufficient funds. Needed: {total_needed}, Available: {transaction.amount}")
    
    try:
        # Record Distribution Event
        event = DistributionEvent(
            transaction_id=transaction.id,
            total_amount=transaction.amount
        )
        db.add(event)
        db.flush() # Get ID

        sum_allocated = Decimal(0)
        for bucket in buckets:
            if bucket.name != "Others":
                monthly_amt = bucket.monthly_amount or Decimal(0)
                bucket.total_amount = (bucket.total_amount or 0) + monthly_amt
                sum_allocated += monthly_amt
                
                # Log entry
                if monthly_amt > 0:
                    db.add(DistributionLog(
                        event_id=event.id,
                        bucket_id=bucket.id,
                        amount=monthly_amt
                    ))
        
        remainder = transaction.amount - sum_allocated
        others_bucket.total_amount = (others_bucket.total_amount or 0) + remainder
        
        # Log remainder
        if remainder > 0:
            db.add(DistributionLog(
                event_id=event.id,
                bucket_id=others_bucket.id,
                amount=remainder
            ))
        
        db.commit()
        return {"message": "Income distributed successfully", "allocated": float(sum_allocated), "remainder": float(remainder)}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transfer")
def transfer_funds(transfer: FundTransfer, db: Session = Depends(get_db)):
    from_bucket = db.query(Bucket).filter(Bucket.id == transfer.from_bucket_id).first()
    to_bucket = db.query(Bucket).filter(Bucket.id == transfer.to_bucket_id).first()
    
    if not from_bucket or not to_bucket:
        raise HTTPException(status_code=404, detail="One or both buckets not found")
    
    amount_to_transfer = Decimal(0)
    
    if transfer.transfer_all:
        amount_to_transfer = from_bucket.total_amount
    elif transfer.amount:
        amount_to_transfer = Decimal(transfer.amount)
    else:
        raise HTTPException(status_code=400, detail="Amount must be provided if transfer_all is False")
        
    if (from_bucket.total_amount or 0) < amount_to_transfer:
        raise HTTPException(status_code=400, detail="Insufficient funds in source bucket")
    
    try:
        from_bucket.total_amount = (from_bucket.total_amount or 0) - amount_to_transfer
        to_bucket.total_amount = (to_bucket.total_amount or 0) + amount_to_transfer
        db.commit()
        return {"message": "Funds transferred successfully", "amount": float(amount_to_transfer)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/buckets/{bucket_id}/reset")
def reset_bucket(bucket_id: int, db: Session = Depends(get_db)):
    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")
    
    if (bucket.total_amount or 0) >= 0:
        raise HTTPException(status_code=400, detail="Bucket balance is not negative")
        
    others = db.query(Bucket).filter(Bucket.name == "Others").first()
    if not others:
        raise HTTPException(status_code=500, detail="Others bucket not found")
        
    amount_needed = abs(bucket.total_amount)
    
    if (others.total_amount or 0) < amount_needed:
        raise HTTPException(status_code=400, detail=f"Insufficient funds in Others. Needed: {amount_needed}, Available: {others.total_amount}")
        
    try:
        others.total_amount -= amount_needed
        bucket.total_amount += amount_needed
        db.commit()
        return {"message": "Bucket reset successfully", "transferred_amount": float(amount_needed)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/distributions/{event_id}/revert")
def revert_distribution(event_id: int, db: Session = Depends(get_db)):
    event = db.query(DistributionEvent).filter(DistributionEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Distribution event not found")
    
    if event.is_reverted:
        raise HTTPException(status_code=400, detail="Distribution already reverted")
        
    try:
        # Revert balances
        for log in event.logs:
            bucket = db.query(Bucket).filter(Bucket.id == log.bucket_id).first()
            if bucket:
                bucket.total_amount = (bucket.total_amount or 0) - log.amount
        
        event.is_reverted = True
        db.commit()
        return {"message": "Distribution reverted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
