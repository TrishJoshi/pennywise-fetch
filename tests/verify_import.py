import json
from app.schemas import PennyWiseBackup
import sys

def verify_import(filename):
    print(f"Reading {filename}...")
    with open(filename, 'r') as f:
        data = json.load(f)
    
    print("Parsing with Pydantic...")
    try:
        backup = PennyWiseBackup(**data)
        
        if not backup.database:
            print("ERROR: No database snapshot found.")
            return

        transactions = backup.database.transactions
        print(f"Found {len(transactions)} transactions.")
        
        if len(transactions) > 0:
            t = transactions[0]
            print("First transaction sample:")
            print(t.model_dump(exclude_unset=True))
            
            # Check if fields are populated
            if t.amount is None and t.merchant_name is None:
                print("ERROR: Transaction fields are empty! Schema mismatch likely persists.")
            else:
                print("SUCCESS: Transaction fields are populated.")
        else:
            print("WARNING: No transactions in list (but might be empty in file).")
            
    except Exception as e:
        print(f"ERROR: Failed to parse: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    filename = "best.pennywisebackup"
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    verify_import(filename)
