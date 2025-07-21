from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Text, DateTime, func, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..db.database import Base

# Import and register the vector type with SQLAlchemy
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # If pgvector is not installed, define a placeholder for development
    # This won't work for actual database operations but allows models to be imported
    class Vector:
        def __init__(self, dimensions):
            self.dimensions = dimensions

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    files = relationship("File", back_populates="user")

class File(Base):
    __tablename__ = "files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String)
    file_path = Column(String)
    file_type = Column(String)
    file_size = Column(Integer)  # size in bytes
    status = Column(String)  # "Pending", "Embedded", "Stored", "Error"
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    user = relationship("User", back_populates="files")
    chunks = relationship("Chunk", back_populates="file")

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_number = Column(Integer)
    text = Column(Text)
    token_count = Column(Integer)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    file = relationship("File", back_populates="chunks")
    embedding = relationship("Embedding", back_populates="chunk", uselist=False)

class Embedding(Base):
    __tablename__ = "embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id"), unique=True)
    embedding_vector = Column(Vector(1536))  # OpenAI embedding size
    embedding_model = Column(String)  # e.g., "text-embedding-ada-002"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chunk = relationship("Chunk", back_populates="embedding")
    
    # Define index for vector similarity searches
    __table_args__ = (
        Index(
            'idx_embeddings_vector',
            embedding_vector,
            postgresql_using='ivfflat',  # Use IVFFlat index for larger datasets
            postgresql_with={'lists': 100},  # Recommended for ~1M vectors
            postgresql_ops={'embedding_vector': 'vector_cosine_ops'}  # Cosine similarity operations
        ),
    )
    
class QueryLog(Base):
    __tablename__ = "query_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_text = Column(Text)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    response = Column(Text, nullable=True)
    response_time = Column(Float, nullable=True)  # in seconds
    relevant_chunk_ids = Column(Text, nullable=True)  # JSON string of relevant chunk IDs
