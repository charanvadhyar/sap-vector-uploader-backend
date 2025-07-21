import logging
import os
import sys
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.database import engine, Base
from app.models.models import File, Chunk, Embedding, User, QueryLog  # Import models to register them

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_pgvector():
    """Initialize pgvector extension in the database."""
    logger.info("Initializing pgvector extension...")
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        logger.info("pgvector extension initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize pgvector extension: {e}")
        return False

def create_tables():
    """Create database tables if they don't exist."""
    logger.info("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False

def check_connection():
    """Check database connection."""
    logger.info("Checking database connection...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            logger.info(f"Database connection successful, result: {result}")
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False

def init_db():
    """Initialize database."""
    if not check_connection():
        logger.error("Database connection check failed. Aborting initialization.")
        return False
    
    pgvector_success = init_pgvector()
    if not pgvector_success:
        logger.error("pgvector initialization failed. Make sure pgvector extension is available in your Neon database.")
        logger.error("You may need to enable it in the Neon console or contact your database administrator.")
        return False
    
    tables_success = create_tables()
    if not tables_success:
        logger.error("Table creation failed.")
        return False
    
    logger.info("Database initialization completed successfully!")
    return True

if __name__ == "__main__":
    success = init_db()
    if not success:
        logger.error("Database initialization failed.")
        sys.exit(1)
    sys.exit(0)
