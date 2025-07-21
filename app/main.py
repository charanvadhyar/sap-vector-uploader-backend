from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from sqlalchemy import text

from .routers import auth, upload, files, chunks, query, process, admin
from .db.database import Base, engine, get_db
from .db.init_db import init_db

logger = logging.getLogger(__name__)

# Initialize database and create tables
try:
    init_result = init_db()
    if not init_result:
        logger.error("Database initialization failed. Application may not function correctly.")
    else:
        logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Error during database initialization: {str(e)}")

# Initialize FastAPI app
app = FastAPI(
    title="SAP FICO Vector Database API",
    description="API for uploading, chunking, and querying SAP FICO documents",
    version="0.1.0",
)

# Configure CORS
origins = [
    "http://localhost:3000",  # Frontend URL
    "http://localhost:8000",  # Backend URL for development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(upload.router)
app.include_router(files.router)
app.include_router(chunks.router)
app.include_router(query.router)
app.include_router(process.router)

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "message": "API is running"}

# Root endpoint
@app.get("/", tags=["root"])
async def root():
    return {
        "message": "Welcome to the SAP FICO Vector Database API",
        "documentation": "/docs",
    }

# Make uploads directory if it doesn't exist
if not os.path.exists("uploads"):
    os.makedirs("uploads")
