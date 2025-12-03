from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.importer import process_backup
from app.schemas import PennyWiseBackup
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_backup(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a JSON file.")

    try:
        content = await file.read()
        data = json.loads(content)
        backup_data = PennyWiseBackup(**data)
        
        # Process synchronously for now to return result, or use background task if it's too long.
        # Given the requirement "reconstruct the details", user might want to know if it succeeded.
        # But for large files, background is better.
        # Let's do it synchronously for simplicity unless it times out, 
        # or we can offload to background and return a job ID.
        # The user said "periodically... db should update".
        # Let's run it and return the status.
        
        process_backup(backup_data, db, file.filename)
        
        return {"message": "Backup processed successfully", "filename": file.filename}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file.")
    except Exception as e:
        logger.error(f"Error processing backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))
