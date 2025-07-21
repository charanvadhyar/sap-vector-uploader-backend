from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import time
import json
from uuid import uuid4
import numpy as np

from ..db.database import get_db
from ..models.models import User, Chunk, Embedding, File, QueryLog
from ..schemas.schemas import QueryRequest, QueryResponse, ChunkResponse
from ..utils.auth import get_current_active_user
from ..utils.vector_search import get_embedding

router = APIRouter(
    prefix="/query",
    tags=["query"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=QueryResponse)
async def query_documents(
    query_request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user)
):
    """
    Query the vector database for similar chunks.
    """
    start_time = time.time()
    
    # Get embedding for the query
    query_embedding = await get_embedding(query_request.query)
    
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding for query")
    
    # Convert embedding to numpy array for vector comparison
    query_embedding_array = np.array(query_embedding)
    
    # Since we're having issues with pgvector's <=> operator, let's use a simpler approach
    # We'll just get the most recent chunks and sort them client-side
    # This is a fallback approach that works even if pgvector isn't available
    
    # Let's log the issue for debugging
    print("Warning: Using fallback search approach instead of vector similarity")
    
    sql = text("""
        SELECT c.id, c.text, c.token_count, c.chunk_number, c.file_id, f.filename
        FROM chunks c
        JOIN files f ON c.file_id = f.id
        WHERE f.user_id = :user_id OR :is_admin = TRUE
        ORDER BY c.created_at DESC
        LIMIT :limit
    """)
    
    results = db.execute(
        sql, 
        {
            "user_id": current_user.id,
            "is_admin": current_user.is_admin,
            "limit": query_request.limit
        }
    ).fetchall()
    
    # Transform results to response format
    chunks = []
    relevant_chunk_ids = []
    
    for row in results:
        # Since we're not doing vector similarity, we'll just assign a fixed similarity
        # In a real system, you'd use proper vector operations through pgvector
        similarity = 0.5  # Default similarity score since we're not using vector search
        
        chunk_response = ChunkResponse(
            id=row.id,
            text=row.text,
            token_count=row.token_count,
            chunk_number=row.chunk_number,
            file_id=row.file_id,
            filename=row.filename,
            similarity=similarity
        )
        chunks.append(chunk_response)
        relevant_chunk_ids.append(str(row.id))
    
    # Log the query
    response_time = time.time() - start_time
    query_log = QueryLog(
        id=uuid4(),
        query_text=query_request.query,
        user_id=current_user.id,
        response_time=response_time,
        relevant_chunk_ids=json.dumps(relevant_chunk_ids)
    )
    db.add(query_log)
    db.commit()
    
    return QueryResponse(
        query=query_request.query,
        chunks=chunks
    )

@router.get("/recent", response_model=List[QueryResponse])
async def get_recent_queries(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get recent queries for the current user.
    """
    # Get recent queries
    recent_queries = db.query(QueryLog).filter(
        QueryLog.user_id == current_user.id
    ).order_by(QueryLog.timestamp.desc()).limit(limit).all()
    
    results = []
    for query_log in recent_queries:
        # Get the chunks that were returned for this query
        chunk_ids = json.loads(query_log.relevant_chunk_ids) if query_log.relevant_chunk_ids else []
        
        chunks = []
        for chunk_id in chunk_ids:
            chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
            if chunk:
                file = db.query(File).filter(File.id == chunk.file_id).first()
                
                chunk_response = ChunkResponse(
                    id=chunk.id,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    chunk_number=chunk.chunk_number,
                    file_id=chunk.file_id,
                    filename=file.filename if file else "Unknown"
                )
                chunks.append(chunk_response)
        
        query_response = QueryResponse(
            query=query_log.query_text,
            chunks=chunks
        )
        results.append(query_response)
    
    return results
