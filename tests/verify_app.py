from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base
import os
import json

# Use the dev DB
DATABASE_URL = "postgresql://postgres:postgres@localhost/pennywise_dev"
os.environ["DATABASE_URL"] = DATABASE_URL

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_upload():
    # Read mock file
    with open("mock_backup.json", "rb") as f:
        response = client.post(
            "/api/v1/upload",
            files={"file": ("mock_backup.json", f, "application/json")}
        )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 200
    
    # Verify DB content
    db = TestingSessionLocal()
    from app.models import Category, Transaction, ImportLog, ImportRowLog
    
    cats = db.query(Category).all()
    print(f"Categories count: {len(cats)}")
    for c in cats:
        print(f" - {c.name}")

    txs = db.query(Transaction).all()
    print(f"Transactions count: {len(txs)}")
    
    logs = db.query(ImportLog).all()
    print(f"Import Logs: {len(logs)}")
    if logs:
        print(f"Log Status: {logs[0].status}")
        row_logs = db.query(ImportRowLog).filter_by(import_log_id=logs[0].id).all()
        print(f"Row Logs: {len(row_logs)}")
        for rl in row_logs:
            print(f" - {rl.action} {rl.table_name}")

if __name__ == "__main__":
    test_upload()
