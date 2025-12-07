import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from datetime import datetime
from app.models import Base, Category, Transaction, Bucket, ImportLog, ImportRowLog
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

@pytest.fixture(autouse=True)
def clear_db(test_db):
    test_db.query(Transaction).delete()
    test_db.query(Category).delete()
    test_db.query(Bucket).delete()
    test_db.query(ImportRowLog).delete()
    test_db.query(ImportLog).delete()
    test_db.commit()

def test_importer_creates_bucket_and_updates_balance(test_db):
    # Create Mock Backup Data
    backup_data = PennyWiseBackup(
        _format="JSON",
        _created="2023-10-27T10:00:00Z",
        database=DatabaseSnapshot(
            categories=[
                CategoryEntity(
                    id=1,
                    name="Test Category",
                    monthly_amount=Decimal("1000.00"),
                    total_amount=Decimal("0.00") # Ignored by importer logic for buckets, but used to create category
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
    
    # Run Importer
    process_backup(backup_data, test_db, "test_backup.json")
    
    # Verify Results
    cat = test_db.query(Category).filter(Category.name == "Test Category").first()
    assert cat is not None
    assert cat.bucket is not None
    
    bucket = cat.bucket
    assert bucket.name == "Test Category"
    
    # Expected: 
    # Initial Bucket Amount: 0.00 (Created fresh)
    # + Income: 500.00
    # - Expense: 200.00
    # Total: 300.00
    
    assert bucket.total_amount == Decimal("300.00")

def test_importer_updates_transaction(test_db):
    # 1. Initial Import
    backup_data_1 = PennyWiseBackup(
        database=DatabaseSnapshot(
            categories=[CategoryEntity(name="Test Category")],
            transactions=[
                TransactionEntity(
                    amount=Decimal("100.00"),
                    merchant_name="Store",
                    category="Test Category",
                    transaction_type="EXPENSE",
                    transaction_hash="tx_1"
                )
            ]
        )
    )
    process_backup(backup_data_1, test_db, "backup1.json")
    
    cat = test_db.query(Category).filter(Category.name == "Test Category").first()
    bucket = cat.bucket
    assert bucket.total_amount == Decimal("-100.00")
    
    # 2. Update Import (Change amount to 150)
    backup_data_2 = PennyWiseBackup(
        database=DatabaseSnapshot(
            categories=[CategoryEntity(name="Test Category")],
            transactions=[
                TransactionEntity(
                    amount=Decimal("150.00"), # Changed
                    merchant_name="Store",
                    category="Test Category",
                    transaction_type="EXPENSE",
                    transaction_hash="tx_1"
                )
            ]
        )
    )
    process_backup(backup_data_2, test_db, "backup2.json")
    
    test_db.refresh(bucket)
    # Expected: -100 (reverted) -> 0 -> -150 (applied)
    # Logic: Revert old (-100 -> +100), Apply new (-150)
    # Current balance was -100. 
    # Revert: -100 + 100 = 0.
    # Apply: 0 - 150 = -150.
    assert bucket.total_amount == Decimal("-150.00")

def test_importer_soft_delete(test_db):
    # 1. Initial Import
    backup_data_1 = PennyWiseBackup(
        database=DatabaseSnapshot(
            categories=[CategoryEntity(name="Test Category")],
            transactions=[
                TransactionEntity(
                    amount=Decimal("100.00"),
                    merchant_name="Store",
                    category="Test Category",
                    transaction_type="EXPENSE",
                    transaction_hash="tx_1"
                )
            ]
        )
    )
    process_backup(backup_data_1, test_db, "backup1.json")
    
    cat = test_db.query(Category).filter(Category.name == "Test Category").first()
    bucket = cat.bucket
    assert bucket.total_amount == Decimal("-100.00")
    
    # 2. Delete Import (Transaction removed from backup)
    backup_data_2 = PennyWiseBackup(
        database=DatabaseSnapshot(
            categories=[CategoryEntity(name="Test Category")],
            transactions=[] # Empty
        )
    )
    process_backup(backup_data_2, test_db, "backup2.json")
    
    # Verify Soft Delete
    tx = test_db.query(Transaction).filter(Transaction.transaction_hash == "tx_1").first()
    assert tx.is_deleted == True
    
    # Verify Balance Revert
    test_db.refresh(bucket)
    # Expected: -100 (reverted) -> 0
    assert bucket.total_amount == Decimal("0.00")
