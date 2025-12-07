import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from app.main import app
from app.database import get_db
from app.models import Category, Base, Bucket

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_reset.db"
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
    bucket_neg = Bucket(name="Overspent Bucket", monthly_amount=1000, total_amount=-500)
    bucket_pos = Bucket(name="Savings Bucket", monthly_amount=2000, total_amount=1000)
    others = Bucket(name="Others", monthly_amount=0, total_amount=1000)
    db.add_all([bucket_neg, bucket_pos, others])
    db.commit()
    db.refresh(bucket_neg)
    db.refresh(bucket_pos)
    db.refresh(others)
    return bucket_neg, bucket_pos, others

def test_reset_bucket_success(test_db):
    bucket_neg, _, others = setup_data(test_db)
    
    response = client.post(f"/api/v1/budget/buckets/{bucket_neg.id}/reset")
    assert response.status_code == 200
    assert response.json()["transferred_amount"] == 500.0
    
    # Verify Balances
    buckets = client.get("/api/v1/budget/buckets").json()
    updated_neg = next(b for b in buckets if b["id"] == bucket_neg.id)
    updated_others = next(b for b in buckets if b["name"] == "Others")
    
    assert float(updated_neg["totalAmount"]) == 0.0
    assert float(updated_others["totalAmount"]) == 500.0 # 1000 - 500

def test_reset_bucket_positive_balance(test_db):
    _, bucket_pos, _ = setup_data(test_db)
    
    response = client.post(f"/api/v1/budget/buckets/{bucket_pos.id}/reset")
    assert response.status_code == 400
    assert "not negative" in response.json()["detail"]

def test_reset_insufficient_funds(test_db):
    # Setup Others
    others = Bucket(name="Others", monthly_amount=0, total_amount=1000)
    test_db.add(others)
    test_db.commit()

    # Create a huge negative balance
    bucket_huge = Bucket(name="Huge Debt Bucket", monthly_amount=0, total_amount=-10000)
    test_db.add(bucket_huge)
    test_db.commit()
    test_db.refresh(bucket_huge)
    
    response = client.post(f"/api/v1/budget/buckets/{bucket_huge.id}/reset")
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]
