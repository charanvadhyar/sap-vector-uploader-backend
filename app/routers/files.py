from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from ..db.database import get_db
from ..models.models import User, File, Chunk
from ..schemas.schemas import FileResponse, FileDetailResponse
from ..utils.auth import get_current_active_user
from ..utils.file_processing import re_process_file

router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[FileResponse])
async def get_all_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Get all files for the current user
    files = db.query(File).filter(File.user_id == current_user.id).all()
    
    # Create response with chunk count for each file
    response = []
    for file in files:
        chunk_count = db.query(Chunk).filter(Chunk.file_id == file.id).count()
        response.append(
            FileResponse(
                id=file.id,
                filename=file.filename,
                file_type=file.file_type,
                file_size=file.file_size,
                status=file.status,
                upload_date=file.upload_date,
                total_chunks=chunk_count
            )
        )
    
    return response

@router.get("/{file_id}", response_model=FileDetailResponse)
async def get_file_details(
    file_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Get file with specified ID for current user
    file = db.query(File).filter(
        File.id == file_id,
        File.user_id == current_user.id
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get chunks for the file
    db_chunks = db.query(Chunk).filter(Chunk.file_id == file.id).order_by(Chunk.chunk_number).all()
    
    # Convert database model objects to Pydantic schema objects
    from ..schemas.schemas import Chunk as ChunkSchema
    
    # Create Pydantic schema objects from database models
    chunk_schemas = [
        ChunkSchema(
            id=chunk.id,
            chunk_number=chunk.chunk_number,
            text=chunk.text,
            token_count=chunk.token_count,
            file_id=chunk.file_id,
            created_at=chunk.created_at
        ) for chunk in db_chunks
    ]
    
    return FileDetailResponse(
        id=file.id,
        filename=file.filename,
        file_type=file.file_type,
        file_size=file.file_size,
        status=file.status,
        upload_date=file.upload_date,
        total_chunks=len(chunk_schemas),
        chunks=chunk_schemas
    )

@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Get file with specified ID for current user
    file = db.query(File).filter(
        File.id == file_id,
        File.user_id == current_user.id
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete all chunks associated with the file
    db.query(Chunk).filter(Chunk.file_id == file.id).delete()
    
    # Delete file record
    db.delete(file)
    db.commit()
    
    # Delete physical file if it exists
    try:
        import os
        if os.path.exists(file.file_path):
            os.remove(file.file_path)
    except Exception as e:
        # Log error but don't fail the request
        print(f"Error deleting file: {e}")
    
    return {"message": "File deleted successfully"}

@router.post("/{file_id}/reprocess", response_model=FileResponse)
async def reprocess_file(
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Get file with specified ID for current user
    file = db.query(File).filter(
        File.id == file_id,
        File.user_id == current_user.id
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Update file status
    file.status = "Pending"
    db.commit()
    
    # Re-process file in background
    background_tasks.add_task(
        re_process_file,
        file_id=file.id,
        file_path=file.file_path,
        db=db
    )
    
    # Get current chunk count
    chunk_count = db.query(Chunk).filter(Chunk.file_id == file.id).count()
    
    return FileResponse(
        id=file.id,
        filename=file.filename,
        file_type=file.file_type,
        file_size=file.file_size,
        status=file.status,
        upload_date=file.upload_date,
        total_chunks=chunk_count
    )
