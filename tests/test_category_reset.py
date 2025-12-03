import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from app.main import app
from app.database import get_db
from app.models import Category, Base

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

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def setup_data(db):
    # Categories
    cat_neg = Category(name="Overspent", monthly_amount=1000, total_amount=-500)
    cat_pos = Category(name="Savings", monthly_amount=2000, total_amount=1000)
    others = Category(name="Others", monthly_amount=0, total_amount=1000)
    db.add_all([cat_neg, cat_pos, others])
    db.commit()
    return cat_neg, cat_pos, others

def test_reset_category_success(test_db):
    cat_neg, _, others = setup_data(test_db)
    
    response = client.post(f"/api/v1/budget/categories/{cat_neg.id}/reset")
    assert response.status_code == 200
    assert response.json()["transferred_amount"] == 500.0
    
    # Verify Balances
    cats = client.get("/api/v1/budget/categories").json()
    updated_neg = next(c for c in cats if c["id"] == cat_neg.id)
    updated_others = next(c for c in cats if c["name"] == "Others")
    
    assert float(updated_neg["totalAmount"]) == 0.0
    assert float(updated_others["totalAmount"]) == 500.0 # 1000 - 500

def test_reset_category_positive_balance(test_db):
    cats = client.get("/api/v1/budget/categories").json()
    cat_pos = next(c for c in cats if c["name"] == "Savings")
    
    response = client.post(f"/api/v1/budget/categories/{cat_pos['id']}/reset")
    assert response.status_code == 400
    assert "not negative" in response.json()["detail"]

def test_reset_insufficient_funds(test_db):
    # Create a huge negative balance
    db = TestingSessionLocal()
    cat_huge = Category(name="Huge Debt", monthly_amount=0, total_amount=-10000)
    db.add(cat_huge)
    db.commit()
    cat_id = cat_huge.id
    db.close()
    
    response = client.post(f"/api/v1/budget/categories/{cat_id}/reset")
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]
