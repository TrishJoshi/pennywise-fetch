import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, engine
from app.models import Category, Transaction, Base, Bucket, DistributionLog, DistributionEvent
from decimal import Decimal
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Setup test DB
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        print("OVERRIDE CALLED")
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def override_dependency():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides = {}

client = TestClient(app)

@pytest.fixture(scope="function")
def test_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Clear existing data
    db.query(DistributionLog).delete()
    db.query(DistributionEvent).delete()
    db.query(Transaction).delete()
    db.query(Category).delete()
    db.query(Bucket).delete()
    db.commit()
    
    yield db
    
    # Cleanup
    db.close()

def test_budget_flow(test_db):
    # 1. Create Buckets and Categories
    bucket1 = Bucket(name="Food Bucket", monthly_amount=1000, total_amount=0)
    bucket2 = Bucket(name="Rent Bucket", monthly_amount=5000, total_amount=0)
    others_bucket = Bucket(name="Others", monthly_amount=0, total_amount=0)
    
    test_db.add_all([bucket1, bucket2, others_bucket])
    test_db.commit()
    
    cat1 = Category(name="Food", bucket_id=bucket1.id)
    cat2 = Category(name="Rent", bucket_id=bucket2.id)
    test_db.add_all([cat1, cat2])
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
    test_db.refresh(bucket1)
    test_db.refresh(bucket2)
    test_db.refresh(others_bucket)
    assert bucket1.total_amount == 1000
    assert bucket2.total_amount == 5000
    assert others_bucket.total_amount == 4000
    
    # 4. Transfer Funds
    # Transfer 500 from Others to Food
    response = client.post("/api/v1/budget/transfer", json={
        "from_bucket_id": others_bucket.id,
        "to_bucket_id": bucket1.id,
        "amount": "500"
    })
    assert response.status_code == 200
    
    test_db.refresh(bucket1)
    test_db.refresh(others_bucket)
    assert bucket1.total_amount == 1500
    assert others_bucket.total_amount == 3500
    
    # 5. Transfer All
    # Transfer all remaining Others to Rent
    response = client.post("/api/v1/budget/transfer", json={
        "from_bucket_id": others_bucket.id,
        "to_bucket_id": bucket2.id,
        "transfer_all": True
    })
    assert response.status_code == 200
    
    test_db.refresh(bucket2)
    test_db.refresh(others_bucket)
    assert bucket2.total_amount == 8500 # 5000 + 3500
    assert others_bucket.total_amount == 0

    # 6. Insufficient Funds Test
    response = client.post("/api/v1/budget/transfer", json={
        "from_bucket_id": others_bucket.id,
        "to_bucket_id": bucket1.id,
        "amount": "100"
    })
    assert response.status_code == 400

def test_insufficient_funds_message(test_db):
    # Create bucket
    bucket = Bucket(name="Luxury Bucket", monthly_amount=1000, total_amount=0)
    others = Bucket(name="Others", monthly_amount=0, total_amount=0) # Needed for distribute logic
    test_db.add_all([bucket, others])
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
    assert "Needed: 1000.00" in response.json()["detail"]
    assert "Available: 500.00" in response.json()["detail"]

def test_get_income_transactions(test_db):
    # Create an income transaction
    tx = Transaction(
        amount=5000,
        merchant_name="Bonus",
        category="Income",
        transaction_type="INCOME",
        transaction_hash="tx_bonus",
        date_time=datetime.utcnow()
    )
    test_db.add(tx)
    test_db.commit()
    
    response = client.get("/api/v1/budget/income-transactions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    merchants = [t["merchantName"] for t in data]
    assert "Bonus" in merchants

def test_get_buckets(test_db):
    bucket = Bucket(name="Food Bucket", monthly_amount=1000, total_amount=0)
    test_db.add(bucket)
    test_db.commit()

    response = client.get("/api/v1/budget/buckets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    names = [b["name"] for b in data]
    assert "Food Bucket" in names
