from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
import os
import shutil
from typing import List
from datetime import datetime
import magic

from ..db.database import get_db
from ..models.models import User, File as FileModel
from ..schemas.schemas import FileResponse
from ..utils.auth import get_current_active_user
from ..utils.file_processing import process_file

router = APIRouter(
    prefix="/upload",
    tags=["upload"],
    responses={404: {"description": "Not found"}},
)

UPLOAD_DIR = "uploads"
# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/", response_model=FileResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Validate file type
    content_type = magic.from_buffer(await file.read(2048), mime=True)
    await file.seek(0)  # Reset file pointer after reading
    
    # Check if file type is allowed
    allowed_types = [
        "application/pdf",  # PDF files
        "text/plain",       # TXT files
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX files
        "application/msword"  # DOC files (legacy)
    ]
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: PDF, TXT, DOCX"
        )
    
    # Create a unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save file to uploads directory
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Determine file extension
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    # Create file record in database
    db_file = FileModel(
        id=uuid4(),
        filename=file.filename,
        file_path=file_path,
        file_type=file_extension[1:] if file_extension else "",  # Remove the dot from extension
        file_size=os.path.getsize(file_path),
        status="Pending",
        user_id=current_user.id
    )
    
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    # Process file in background
    background_tasks.add_task(
        process_file,
        file_id=db_file.id,
        file_path=file_path,
        db=db
    )
    
    return FileResponse(
        id=db_file.id,
        filename=db_file.filename,
        file_type=db_file.file_type,
        file_size=db_file.file_size,
        status=db_file.status,
        upload_date=db_file.upload_date,
        total_chunks=0  # No chunks yet as processing is async
    )

@router.get("/{file_id}/status", response_model=FileResponse)
async def check_upload_status(
    file_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Get file from database
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id, 
        FileModel.user_id == current_user.id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Count chunks for the file
    total_chunks = len(db_file.chunks)
    
    return FileResponse(
        id=db_file.id,
        filename=db_file.filename,
        file_type=db_file.file_type,
        file_size=db_file.file_size,
        status=db_file.status,
        upload_date=db_file.upload_date,
        total_chunks=total_chunks
    )
