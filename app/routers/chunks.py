from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from ..db.database import get_db
from ..models.models import User, File, Chunk, Embedding
from ..schemas.schemas import Chunk as ChunkSchema, ChunkWithEmbedding
from ..utils.auth import get_current_active_user, get_admin_user

router = APIRouter(
    prefix="/chunks",
    tags=["chunks"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[ChunkWithEmbedding])
async def get_all_chunks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)  # Admin only endpoint
):
    """
    Get all chunks across all files (admin only).
    """
    chunks = db.query(Chunk).offset(skip).limit(limit).all()
    
    # Create response with embedding info
    result = []
    for chunk in chunks:
        embedding = db.query(Embedding).filter(Embedding.chunk_id == chunk.id).first()
        
        chunk_with_embedding = ChunkWithEmbedding(
            id=chunk.id,
            chunk_number=chunk.chunk_number,
            text=chunk.text,
            token_count=chunk.token_count,
            file_id=chunk.file_id,
            created_at=chunk.created_at,
            embedding_id=embedding.id if embedding else None,
            embedding_model=embedding.embedding_model if embedding else None
        )
        result.append(chunk_with_embedding)
    
    return result

@router.get("/{chunk_id}", response_model=ChunkWithEmbedding)
async def get_chunk(
    chunk_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific chunk by ID.
    """
    # First, get the chunk
    chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    # Check if user has access to this chunk's file
    file = db.query(File).filter(File.id == chunk.file_id).first()
    if not file or (not current_user.is_admin and file.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to access this chunk")
    
    # Get embedding information if it exists
    embedding = db.query(Embedding).filter(Embedding.chunk_id == chunk.id).first()
    
    return ChunkWithEmbedding(
        id=chunk.id,
        chunk_number=chunk.chunk_number,
        text=chunk.text,
        token_count=chunk.token_count,
        file_id=chunk.file_id,
        created_at=chunk.created_at,
        embedding_id=embedding.id if embedding else None,
        embedding_model=embedding.embedding_model if embedding else None
    )

@router.get("/file/{file_id}", response_model=List[ChunkSchema])
async def get_file_chunks(
    file_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all chunks for a specific file.
    """
    # Check if file exists and user has access
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not current_user.is_admin and file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this file")
    
    # Get chunks for the file
    chunks = db.query(Chunk).filter(Chunk.file_id == file_id).order_by(Chunk.chunk_number).all()
    
    return chunks
