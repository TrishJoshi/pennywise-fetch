import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from decimal import Decimal
from app.main import app
from app.database import get_db
from app.models import Category, Transaction, Base, DistributionEvent, DistributionLog, Bucket

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_distribution.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
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
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def setup_data(db):
    # Buckets
    bucket1 = Bucket(name="Food Bucket", monthly_amount=1000, total_amount=0)
    bucket2 = Bucket(name="Rent Bucket", monthly_amount=2000, total_amount=0)
    others = Bucket(name="Others", monthly_amount=0, total_amount=0)
    db.add_all([bucket1, bucket2, others])
    db.commit()
    
    # Income Transaction
    tx = Transaction(
        amount=5000,
        merchant_name="Salary",
        category="Income",
        transaction_type="INCOME",
        transaction_hash="tx_salary_dist",
        date_time=datetime.now()
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx

def test_distribution_tracking_and_revert(test_db):
    tx = setup_data(test_db)
    
    # 1. Distribute Income
    response = client.post("/api/v1/budget/distribute", json={"transaction_id": tx.id})
    assert response.status_code == 200
    
    # Verify Balances
    buckets = client.get("/api/v1/budget/buckets").json()
    food = next(b for b in buckets if b["name"] == "Food Bucket")
    rent = next(b for b in buckets if b["name"] == "Rent Bucket")
    others = next(b for b in buckets if b["name"] == "Others")
    
    assert float(food["totalAmount"]) == 1000.0
    assert float(rent["totalAmount"]) == 2000.0
    assert float(others["totalAmount"]) == 2000.0 # 5000 - 3000
    
    # 2. Verify History
    response = client.get("/api/v1/budget/distributions")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    event = events[0]
    assert event["totalAmount"] == "5000.00"
    assert event["isReverted"] is False
    assert len(event["logs"]) >= 2
    
    # 3. Revert Distribution
    response = client.post(f"/api/v1/budget/distributions/{event['id']}/revert")
    assert response.status_code == 200
    
    # 4. Verify Revert
    # Check Balances (should be 0)
    buckets = client.get("/api/v1/budget/buckets").json()
    food = next(b for b in buckets if b["name"] == "Food Bucket")
    rent = next(b for b in buckets if b["name"] == "Rent Bucket")
    others = next(b for b in buckets if b["name"] == "Others")
    
    assert float(food["totalAmount"]) == 0.0
    assert float(rent["totalAmount"]) == 0.0
    assert float(others["totalAmount"]) == 0.0
    
    # Check Event Status
    response = client.get("/api/v1/budget/distributions")
    event = response.json()[0]
    assert event["isReverted"] is True

def test_revert_already_reverted(test_db):
    tx = setup_data(test_db)
    
    # Distribute
    response = client.post("/api/v1/budget/distribute", json={"transaction_id": tx.id})
    assert response.status_code == 200
    
    # Get event
    response = client.get("/api/v1/budget/distributions")
    event = response.json()[0]
    
    # Revert
    response = client.post(f"/api/v1/budget/distributions/{event['id']}/revert")
    assert response.status_code == 200
    
    # Try to revert again
    response = client.post(f"/api/v1/budget/distributions/{event['id']}/revert")
    assert response.status_code == 400
    assert "already reverted" in response.json()["detail"]
