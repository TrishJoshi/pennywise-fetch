from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Category, Transaction
from app.schemas import CategoryEntity, BudgetUpdate, FundTransfer, DistributeIncomeRequest, TransactionEntity
from decimal import Decimal
from typing import List
from sqlalchemy import desc
from app.models import Category, Transaction, DistributionEvent, DistributionLog
from app.schemas import (
    CategoryEntity, 
    BudgetUpdate, 
    FundTransfer, 
    DistributeIncomeRequest, 
    TransactionEntity,
    DistributionEventEntity
)

router = APIRouter(
    prefix="/budget",
    tags=["budget"],
    responses={404: {"description": "Not found"}},
)

@router.get("/categories", response_model=List[CategoryEntity])
def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.display_order).all()

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
                "categoryName": log.category.name,
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

@router.put("/categories/{category_id}", response_model=CategoryEntity)
def update_category_budget(category_id: int, budget: BudgetUpdate, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category.monthly_amount = Decimal(budget.monthly_amount)
    db.commit()
    db.refresh(category)
    return category

@router.post("/distribute")
def distribute_income(request: DistributeIncomeRequest, db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == request.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction.category != "Income" or transaction.transaction_type != "INCOME":
        raise HTTPException(status_code=400, detail="Transaction must be of category 'Income' and type 'INCOME'")
    
    categories = db.query(Category).all()
    others_category = next((c for c in categories if c.name == "Others"), None)
    
    if not others_category:
        # Create Others category if it doesn't exist
        others_category = Category(name="Others", is_system=True, is_income=False)
        db.add(others_category)
        db.flush()
        categories.append(others_category)

    total_needed = sum((c.monthly_amount or Decimal(0)) for c in categories if c.name != "Others")
    
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
        for category in categories:
            if category.name != "Others":
                monthly_amt = category.monthly_amount or Decimal(0)
                category.total_amount = (category.total_amount or 0) + monthly_amt
                sum_allocated += monthly_amt
                
                # Log entry
                if monthly_amt > 0:
                    db.add(DistributionLog(
                        event_id=event.id,
                        category_id=category.id,
                        amount=monthly_amt
                    ))
        
        remainder = transaction.amount - sum_allocated
        others_category.total_amount = (others_category.total_amount or 0) + remainder
        
        # Log remainder
        if remainder > 0:
            db.add(DistributionLog(
                event_id=event.id,
                category_id=others_category.id,
                amount=remainder
            ))
        
        db.commit()
        return {"message": "Income distributed successfully", "allocated": float(sum_allocated), "remainder": float(remainder)}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transfer")
def transfer_funds(transfer: FundTransfer, db: Session = Depends(get_db)):
    from_category = db.query(Category).filter(Category.id == transfer.from_category_id).first()
    to_category = db.query(Category).filter(Category.id == transfer.to_category_id).first()
    
    if not from_category or not to_category:
        raise HTTPException(status_code=404, detail="One or both categories not found")
    
    amount_to_transfer = Decimal(0)
    
    if transfer.transfer_all:
        amount_to_transfer = from_category.total_amount
    elif transfer.amount:
        amount_to_transfer = Decimal(transfer.amount)
    else:
        raise HTTPException(status_code=400, detail="Amount must be provided if transfer_all is False")
        
    if (from_category.total_amount or 0) < amount_to_transfer:
        raise HTTPException(status_code=400, detail="Insufficient funds in source category")
    
    try:
        from_category.total_amount = (from_category.total_amount or 0) - amount_to_transfer
        to_category.total_amount = (to_category.total_amount or 0) + amount_to_transfer
        db.commit()
        return {"message": "Funds transferred successfully", "amount": float(amount_to_transfer)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/categories/{category_id}/reset")
def reset_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if (category.total_amount or 0) >= 0:
        raise HTTPException(status_code=400, detail="Category balance is not negative")
        
    others = db.query(Category).filter(Category.name == "Others").first()
    if not others:
        raise HTTPException(status_code=500, detail="Others category not found")
        
    amount_needed = abs(category.total_amount)
    
    if (others.total_amount or 0) < amount_needed:
        raise HTTPException(status_code=400, detail=f"Insufficient funds in Others. Needed: {amount_needed}, Available: {others.total_amount}")
        
    try:
        others.total_amount -= amount_needed
        category.total_amount += amount_needed
        db.commit()
        return {"message": "Category reset successfully", "transferred_amount": float(amount_needed)}
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
            category = db.query(Category).filter(Category.id == log.category_id).first()
            if category:
                category.total_amount = (category.total_amount or 0) - log.amount
        
        event.is_reverted = True
        db.commit()
        return {"message": "Distribution reverted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
