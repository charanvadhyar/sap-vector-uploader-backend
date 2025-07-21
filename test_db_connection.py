import os
import asyncio
import re
from sqlalchemy import text
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

# Load environment variables - force reload to ensure we get the latest values
load_dotenv(override=True)

# Print .env file path to verify it's loading the correct one
print(f"Loading .env from directory: {os.path.abspath('.')}")
# Debug print for DATABASE_URL to verify it's being read correctly (redacting password)
db_url = os.getenv('DATABASE_URL')
if db_url:
    # Safely redact password before printing
    parts = db_url.split('@')
    if len(parts) > 1:
        auth_parts = parts[0].split(':')
        if len(auth_parts) > 2:
            redacted_url = f"{auth_parts[0]}:{auth_parts[1]}:****@{parts[1]}"
            print(f"Found DATABASE_URL with host: {redacted_url.split('@')[1].split('/')[0]}")
    else:
        print("DATABASE_URL format is unexpected")
else:
    print("DATABASE_URL not found in .env file")

async def test_connection() -> None:
    """Test connection to Neon PostgreSQL database."""
    print("Testing connection to Neon PostgreSQL database...")
    
    # Get the actual DATABASE_URL from .env
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL not found in .env file!")
        return
        
    # Show what we're connecting to (redacted)
    host_part = db_url.split('@')[1].split('/')[0] if '@' in db_url else "unknown"
    print(f"Attempting to connect to: {host_part}")
    
    # Convert the standard connection string to asyncpg format
    base_url = re.sub(r'^postgresql:', 'postgresql+asyncpg:', db_url)
    # Remove ssl parameters that asyncpg doesn't handle in the URL
    async_db_url = re.sub(r'[?&]sslmode=require(&channel_binding=require)?', '', base_url)
    
    try:
        engine = create_async_engine(
            async_db_url, 
            echo=True,
            connect_args={
                "ssl": True  # Enable SSL for asyncpg
            }
        )
        async with engine.connect() as conn:
            # Check if pgvector is available
            try:
                result = await conn.execute(text("SELECT 'Connection successful'"))
                print("Basic connection test:", result.scalar())
                
                result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
                if result.scalar():
                    print("✅ pgvector extension is enabled!")
                else:
                    print("❌ pgvector extension is NOT enabled. Please enable it in the Neon dashboard.")
                
                # Test database version
                result = await conn.execute(text("SELECT version()"))
                print("PostgreSQL version:", result.scalar())
                
            except Exception as e:
                print(f"Error during database tests: {e}")
        
        await engine.dispose()
        print("Connection test completed.")
    except Exception as e:
        print(f"Failed to connect to database: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
