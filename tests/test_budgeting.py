import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, engine
from app.models import Category, Transaction, Base
from decimal import Decimal
from sqlalchemy.orm import sessionmaker

# Setup test DB
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module")
def test_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Clear existing data
    db.query(Transaction).delete()
    db.query(Category).delete()
    db.commit()
    
    yield db
    
    # Cleanup
    db.close()

def test_budget_flow(test_db):
    # 1. Create Categories
    cat1 = Category(name="Food", monthly_amount=1000, total_amount=0)
    cat2 = Category(name="Rent", monthly_amount=5000, total_amount=0)
    others = Category(name="Others", monthly_amount=0, total_amount=0)
    test_db.add_all([cat1, cat2, others])
    test_db.commit()
    
    # 2. Create Income Transaction
    income_tx = Transaction(
        amount=10000,
        merchant_name="Salary",
        category="Income",
        transaction_type="INCOME",
        transaction_hash="tx1"
    )
    test_db.add(income_tx)
    test_db.commit()
    
    # 3. Distribute Income
    response = client.post("/api/v1/budget/distribute", json={"transaction_id": income_tx.id})
    assert response.status_code == 200
    data = response.json()
    assert data["allocated"] == 6000.0 # 1000 + 5000
    assert data["remainder"] == 4000.0 # 10000 - 6000
    
    # Verify DB updates
    test_db.refresh(cat1)
    test_db.refresh(cat2)
    test_db.refresh(others)
    assert cat1.total_amount == 1000
    assert cat2.total_amount == 5000
    assert others.total_amount == 4000
    
    # 4. Transfer Funds
    # Transfer 500 from Others to Food
    response = client.post("/api/v1/budget/transfer", json={
        "from_category_id": others.id,
        "to_category_id": cat1.id,
        "amount": "500"
    })
    assert response.status_code == 200
    
    test_db.refresh(cat1)
    test_db.refresh(others)
    assert cat1.total_amount == 1500
    assert others.total_amount == 3500
    
    # 5. Transfer All
    # Transfer all remaining Others to Rent
    response = client.post("/api/v1/budget/transfer", json={
        "from_category_id": others.id,
        "to_category_id": cat2.id,
        "transfer_all": True
    })
    assert response.status_code == 200
    
    test_db.refresh(cat2)
    test_db.refresh(others)
    assert cat2.total_amount == 8500 # 5000 + 3500
    assert others.total_amount == 0

    # 6. Insufficient Funds Test
    response = client.post("/api/v1/budget/transfer", json={
        "from_category_id": others.id,
        "to_category_id": cat1.id,
        "amount": "100"
    })
    assert response.status_code == 400

def test_insufficient_funds_message(test_db):
    # Create categories
    cat = Category(name="Luxury", monthly_amount=1000, total_amount=0)
    test_db.add(cat)
    test_db.commit()
    
    # Create Income with insufficient amount
    income_tx = Transaction(
        amount=500,
        merchant_name="Small Salary",
        category="Income",
        transaction_type="INCOME",
        transaction_hash="tx_small"
    )
    test_db.add(income_tx)
    test_db.commit()
    
    # Try to distribute
    response = client.post("/api/v1/budget/distribute", json={"transaction_id": income_tx.id})
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]
    assert "Needed: 7000.00" in response.json()["detail"]
    assert "Available: 500.00" in response.json()["detail"]
