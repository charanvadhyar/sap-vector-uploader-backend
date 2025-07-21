from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import os

from ..db.database import get_db, get_async_db
from ..models.models import User, File, Chunk, Embedding
from ..schemas.schemas import FileResponse, ProcessingResponse
from ..utils.auth import get_current_active_user
from ..utils.file_processing import process_file, extract_text_from_file, chunk_text
from ..utils.vector_search import get_embedding

router = APIRouter(
    prefix="/process",
    tags=["process"],
    responses={404: {"description": "Not found"}},
)

@router.post("/{file_id}", response_model=ProcessingResponse)
async def process_file_endpoint(
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Process a file by:
    - Reading the uploaded file based on ID
    - Converting it to plain text (PDF, DOCX, TXT)
    - Splitting text into chunks (max 512 tokens)
    - Generating OpenAI embeddings for each chunk
    - Saving the chunks and embeddings to the database with file_id reference
    """
    # Get file with specified ID for current user
    file = db.query(File).filter(
        File.id == file_id,
        File.user_id == current_user.id
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file exists
    if not os.path.exists(file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Update file status
    file.status = "Processing"
    db.commit()
    
    # Process file in background
    background_tasks.add_task(
        process_file,
        file_id=file.id,
        file_path=file.file_path,
        db=db
    )
    
    return ProcessingResponse(
        id=file.id,
        filename=file.filename,
        status="Processing",
        message="File processing started in the background"
    )

@router.post("/{file_id}/sync", response_model=ProcessingResponse)
async def process_file_sync_endpoint(
    file_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Process a file synchronously (wait for completion):
    - Reading the uploaded file based on ID
    - Converting it to plain text (PDF, DOCX, TXT)
    - Splitting text into chunks (max 512 tokens)
    - Generating OpenAI embeddings for each chunk
    - Saving the chunks and embeddings to the database with file_id reference
    """
    # Get file with specified ID for current user
    result = await db.execute(
        File.__table__.select().where(
            (File.id == file_id) & 
            (File.user_id == current_user.id)
        )
    )
    file = result.fetchone()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file exists
    if not os.path.exists(file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Update file status
    await db.execute(
        File.__table__.update().where(File.id == file_id).values(status="Processing")
    )
    await db.commit()
    
    try:
        # Extract text from file
        text = await extract_text_from_file(file.file_path)
        if text.startswith("Error:"):
            await db.execute(
                File.__table__.update().where(File.id == file_id).values(status="Error")
            )
            await db.commit()
            return ProcessingResponse(
                id=file_id,
                filename=file.filename,
                status="Error",
                message=f"Error extracting text: {text}"
            )
        
        # Split text into chunks (max 512 tokens)
        chunks = await chunk_text(text, chunk_size=512, chunk_overlap=50)
        
        # Clear existing chunks for this file if any
        await db.execute(
            Chunk.__table__.delete().where(Chunk.file_id == file_id)
        )
        await db.commit()
        
        # Save chunks and generate embeddings
        chunk_count = 0
        for i, chunk_text_content in enumerate(chunks):
            # Count tokens
            from ..utils.file_processing import count_tokens
            token_count = count_tokens(chunk_text_content)
            
            # Create chunk
            chunk_id = UUID()
            await db.execute(
                Chunk.__table__.insert().values(
                    id=chunk_id,
                    chunk_number=i + 1,
                    text=chunk_text_content,
                    token_count=token_count,
                    file_id=file_id
                )
            )
            
            # Generate embedding
            embedding_vector = await get_embedding(chunk_text_content)
            if embedding_vector:
                await db.execute(
                    Embedding.__table__.insert().values(
                        id=UUID(),
                        chunk_id=chunk_id,
                        embedding_vector=embedding_vector,
                        embedding_model="text-embedding-ada-002"
                    )
                )
                chunk_count += 1
            
            # Commit in batches to avoid large transactions
            if i % 10 == 0:
                await db.commit()
        
        # Final commit
        await db.commit()
        
        # Update file status to embedded
        await db.execute(
            File.__table__.update().where(File.id == file_id).values(status="Embedded")
        )
        await db.commit()
        
        return ProcessingResponse(
            id=file_id,
            filename=file.filename,
            status="Embedded",
            message=f"Successfully processed {chunk_count} chunks"
        )
        
    except Exception as e:
        # Update file status to error
        await db.execute(
            File.__table__.update().where(File.id == file_id).values(status="Error")
        )
        await db.commit()
        
        return ProcessingResponse(
            id=file_id,
            filename=file.filename,
            status="Error",
            message=f"Error processing file: {str(e)}"
        )
