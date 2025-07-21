import os
import re
import logging
from dotenv import load_dotenv
from typing import AsyncGenerator

# SQLAlchemy imports for both sync and async operations
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get the database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set!")
    raise ValueError("DATABASE_URL environment variable not set")

# Create async database URL by converting postgresql:// to postgresql+asyncpg://
# And removing ssl parameters that asyncpg doesn't accept in the URL
base_url = re.sub(r'^postgresql:', 'postgresql+asyncpg:', DATABASE_URL)
# Remove ssl parameters that asyncpg doesn't handle in the URL
ASYNC_DATABASE_URL = re.sub(r'[?&]sslmode=require(&channel_binding=require)?', '', base_url)

# For sync operations (like migrations and some utility functions)
try:
    # Sync engine for operations that require it
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DEBUG", "False").lower() == "true",
        connect_args={
            "sslmode": "require"  # Required for Neon PostgreSQL
        },
        pool_pre_ping=True,  # Verify connection before using from pool
        pool_recycle=300,    # Recycle connections every 5 minutes
    )
    
    # Async engine for main application operations
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=os.getenv("DEBUG", "False").lower() == "true",
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "ssl": True  # Enable SSL for asyncpg
        }
    )
    
    logger.info("Database engines created successfully")
except Exception as e:
    logger.error(f"Failed to create database engines: {e}")
    raise

# Create session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# Base class for models
Base = declarative_base()

# Dependency for synchronous DB access (used in non-async functions)
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()

# Dependency for asynchronous DB access (preferred for FastAPI endpoints)
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database session error: {e}")
            await session.rollback()
            raise
