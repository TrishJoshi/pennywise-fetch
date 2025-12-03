import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from decimal import Decimal
from app.main import app
from app.database import get_db
from app.models import Category, Transaction, Base

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_comprehensive.db"
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

def setup_mock_data(db):
    # Create Categories based on backup structure
    categories = [
        Category(name="Income", is_income=True, monthly_amount=0, total_amount=0),
        Category(name="Others", is_income=False, monthly_amount=0, total_amount=0),
        Category(name="Food & Dining", is_income=False, monthly_amount=5000, total_amount=0),
        Category(name="Transportation", is_income=False, monthly_amount=2000, total_amount=0),
        Category(name="Shopping", is_income=False, monthly_amount=None, total_amount=0), # Test None handling
    ]
    for cat in categories:
        db.add(cat)
    
    # Create Transactions based on backup
    transactions = [
        Transaction(
            amount=10000.00,
            merchant_name="Salary",
            category="Income",
            transaction_type="INCOME",
            transaction_hash="tx_salary_1",
            date_time=datetime.now()
        ),
        Transaction(
            amount=1574.50,
            merchant_name="IRCTC",
            category="Transportation",
            transaction_type="EXPENSE",
            transaction_hash="tx_irctc_1",
            date_time=datetime.now()
        )
    ]
    for tx in transactions:
        db.add(tx)
    db.commit()

def test_full_budget_flow(test_db):
    setup_mock_data(test_db)
    
    # 1. Verify Categories
    response = client.get("/api/v1/budget/categories")
    assert response.status_code == 200
    cats = response.json()
    assert len(cats) >= 5
    
    # 2. Verify Income Transactions
    response = client.get("/api/v1/budget/income-transactions")
    assert response.status_code == 200
    txs = response.json()
    assert len(txs) >= 1
    salary_tx = next(t for t in txs if t["merchantName"] == "Salary")
    
    # 3. Distribute Income (Should succeed even with None monthly_amount)
    # Total needed: 5000 (Food) + 2000 (Transport) + 0 (Shopping/None) = 7000
    # Available: 10000
    # Remainder: 3000 -> Others
    response = client.post("/api/v1/budget/distribute", json={"transaction_id": salary_tx["id"]})
    assert response.status_code == 200
    data = response.json()
    assert data["allocated"] == 7000.0
    assert data["remainder"] == 3000.0
    
    # Verify balances
    response = client.get("/api/v1/budget/categories")
    cats = response.json()
    food = next(c for c in cats if c["name"] == "Food & Dining")
    others = next(c for c in cats if c["name"] == "Others")
    shopping = next(c for c in cats if c["name"] == "Shopping")
    
    assert float(food["totalAmount"]) == 5000.0
    assert float(others["totalAmount"]) == 3000.0
    assert float(shopping["totalAmount"]) == 0.0

def test_insufficient_funds_error(test_db):
    # Create small income
    tx = Transaction(
        amount=100.00,
        merchant_name="Small Gift",
        category="Income",
        transaction_type="INCOME",
        transaction_hash="tx_small_1",
        date_time=datetime.now()
    )
    test_db.add(tx)
    test_db.commit()
    
    # Try to distribute (Need 7000)
    response = client.post("/api/v1/budget/distribute", json={"transaction_id": tx.id})
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]

def test_transfer_funds(test_db):
    # Transfer from Others (3000) to Shopping (0)
    # Get IDs
    cats = client.get("/api/v1/budget/categories").json()
    others_id = next(c["id"] for c in cats if c["name"] == "Others")
    shopping_id = next(c["id"] for c in cats if c["name"] == "Shopping")
    
    response = client.post("/api/v1/budget/transfer", json={
        "from_category_id": others_id,
        "to_category_id": shopping_id,
        "amount": "500.00"
    })
    assert response.status_code == 200
    
    # Verify
    cats = client.get("/api/v1/budget/categories").json()
    others = next(c for c in cats if c["name"] == "Others")
    shopping = next(c for c in cats if c["name"] == "Shopping")
    
    assert float(others["totalAmount"]) == 2500.0
    assert float(shopping["totalAmount"]) == 500.0

def test_frontend_assets_exist():
    # Basic check that frontend files are served
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
