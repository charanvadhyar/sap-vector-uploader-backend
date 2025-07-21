from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_admin: bool = False


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Admin schemas
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    password: Optional[str] = None


class PasswordReset(BaseModel):
    password: str


class FileBase(BaseModel):
    filename: str
    file_type: str


class FileCreate(FileBase):
    pass


class File(FileBase):
    id: UUID
    file_size: int
    status: str
    upload_date: datetime
    user_id: UUID

    class Config:
        orm_mode = True


class ChunkBase(BaseModel):
    chunk_number: int
    text: str
    token_count: int


class ChunkCreate(ChunkBase):
    file_id: UUID


class Chunk(ChunkBase):
    id: UUID
    file_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True


class ChunkWithEmbedding(Chunk):
    embedding_id: Optional[UUID] = None
    embedding_model: Optional[str] = None

    class Config:
        orm_mode = True


class EmbeddingBase(BaseModel):
    chunk_id: UUID
    embedding_model: str


class EmbeddingCreate(EmbeddingBase):
    embedding_vector: List[float]


class Embedding(EmbeddingBase):
    id: UUID
    created_at: datetime

    class Config:
        orm_mode = True


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class ChunkResponse(BaseModel):
    id: UUID
    text: str
    token_count: int
    chunk_number: int
    file_id: UUID
    filename: str
    similarity: Optional[float] = None


class QueryResponse(BaseModel):
    query: str
    chunks: List[ChunkResponse]


class FileResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    upload_date: datetime
    total_chunks: int

    class Config:
        orm_mode = True


class FileDetailResponse(FileResponse):
    chunks: List[Chunk] = []

    class Config:
        orm_mode = True


class ProcessingResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    message: str
    
    class Config:
        orm_mode = True
