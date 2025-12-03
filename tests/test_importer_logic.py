import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from datetime import datetime
from app.models import Base, Category, Transaction
from app.services.importer import process_backup
from app.schemas import PennyWiseBackup, DatabaseSnapshot, TransactionEntity, CategoryEntity

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_importer.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_importer_income_expense_logic(test_db):
    # 1. Setup Initial Data (Category)
    # We can rely on the importer to create the category if it's in the backup, 
    # but let's pre-create it to verify updates or just let importer handle it.
    # Let's let importer create it first.
    
    # 2. Create Mock Backup Data
    backup_data = PennyWiseBackup(
        _format="JSON",
        _created="2023-10-27T10:00:00Z",
        database=DatabaseSnapshot(
            categories=[
                CategoryEntity(
                    id=1,
                    name="Test Category",
                    monthly_amount=Decimal("1000.00"),
                    total_amount=Decimal("0.00") # Initial amount in backup
                )
            ],
            transactions=[
                TransactionEntity(
                    amount=Decimal("500.00"),
                    merchant_name="Salary",
                    category="Test Category",
                    transaction_type="INCOME",
                    transaction_hash="tx_income_1",
                    date_time=datetime.now()
                ),
                TransactionEntity(
                    amount=Decimal("200.00"),
                    merchant_name="Grocery",
                    category="Test Category",
                    transaction_type="EXPENSE",
                    transaction_hash="tx_expense_1",
                    date_time=datetime.now()
                )
            ]
        )
    )
    
    # 3. Run Importer
    process_backup(backup_data, test_db, "test_backup.json")
    
    # 4. Verify Results
    cat = test_db.query(Category).filter(Category.name == "Test Category").first()
    assert cat is not None
    
    # Expected: 
    # Initial (from backup category): 0.00
    # + Income: 500.00
    # - Expense: 200.00
    # Total: 300.00
    
    assert cat.total_amount == Decimal("300.00")

def test_importer_existing_category_update(test_db):
    # Test case where category already exists with some amount
    cat = Category(name="Existing Cat", total_amount=100)
    test_db.add(cat)
    test_db.commit()
    
    backup_data = PennyWiseBackup(
        database=DatabaseSnapshot(
            categories=[
                CategoryEntity(name="Existing Cat", total_amount=Decimal("100.00")) 
                # Importer updates existing category with backup value first (100), then applies transactions
            ],
            transactions=[
                TransactionEntity(
                    amount=Decimal("50.00"),
                    merchant_name="Existing Merchant",
                    category="Existing Cat",
                    transaction_type="INCOME",
                    transaction_hash="tx_income_2"
                )
            ]
        )
    )
    
    process_backup(backup_data, test_db, "test_backup_2.json")
    
    cat = test_db.query(Category).filter(Category.name == "Existing Cat").first()
    # 100 (initial/backup) + 50 (income) = 150
    assert cat.total_amount == Decimal("150.00")
