import os
import random
import logging
from typing import List, Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vector_search")

# Load environment variables
load_dotenv()

# Check if we have an OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_MOCK_EMBEDDINGS = OPENAI_API_KEY is None or OPENAI_API_KEY == ""

# Log OpenAI API key status (safely)
if USE_MOCK_EMBEDDINGS:
    logger.warning("No valid OpenAI API key found in environment variables. Will use mock embeddings.")
    # Print directly to console for debugging
    print("WARNING: No valid OpenAI API key found. OPENAI_API_KEY environment variable is missing or empty.")
    print(f"Current value: '{OPENAI_API_KEY}'")
else:
    logger.info(f"OpenAI API key loaded. Key starts with: {OPENAI_API_KEY[:5]}... and is {len(OPENAI_API_KEY)} characters long.")
    # Print directly to console for debugging
    print(f"INFO: OpenAI API key loaded. Key starts with: {OPENAI_API_KEY[:5]}... and is {len(OPENAI_API_KEY)} characters long.")

# Import OpenAI only if we're not using mock embeddings
if not USE_MOCK_EMBEDDINGS:
    try:
        import openai
        # Set OpenAI API key
        openai.api_key = OPENAI_API_KEY
        logger.info("OpenAI package imported and API key set successfully")
    except ImportError as e:
        logger.error(f"Failed to import OpenAI package: {str(e)}")
        USE_MOCK_EMBEDDINGS = True
    except Exception as e:
        logger.error(f"Error setting up OpenAI: {str(e)}")
        USE_MOCK_EMBEDDINGS = True

def get_mock_embedding(text: str, vector_size: int = 1536) -> List[float]:
    """
    Generate a deterministic mock embedding based on the input text.
    For development/testing use only.
    
    Args:
        text: The text to generate a mock embedding for
        vector_size: Size of the embedding vector (default 1536 to match OpenAI's ada-002)
        
    Returns:
        List[float]: A deterministic mock embedding vector
    """
    # Use the text to seed the random number generator for deterministic results
    random.seed(text)
    
    # Generate mock embedding
    mock_embedding = [random.uniform(-1, 1) for _ in range(vector_size)]
    
    # Normalize the vector
    magnitude = sum(x**2 for x in mock_embedding) ** 0.5
    normalized = [x / magnitude for x in mock_embedding]
    
    return normalized

async def get_embedding(text: str) -> Optional[List[float]]:
    """
    Get an embedding vector for a text using OpenAI's embedding model.
    Falls back to mock embeddings if OpenAI API key is not available.
    
    Args:
        text: The text to embed
        
    Returns:
        List[float]: The embedding vector or None if the API call fails
    """
    try:
        # Ensure text is not empty
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
            
        # Truncate if text is too long
        original_len = len(text)
        if original_len > 8000:
            logger.info(f"Text too long for embedding ({original_len} chars), truncating to 8000 chars")
            text = text[:8000]
        
        # Use mock embeddings if OpenAI API key is not available
        if USE_MOCK_EMBEDDINGS:
            logger.info("Using mock embeddings for development")
            mock_result = get_mock_embedding(text)
            logger.info(f"Successfully generated mock embedding with {len(mock_result)} dimensions")
            return mock_result
        
        # Log attempt to call OpenAI API   
        logger.info(f"Calling OpenAI API for embedding generation with text length: {len(text)}")
        
        try:
            # Call OpenAI API to get embedding
            response = openai.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            
            # Extract embedding from response
            embedding = response.data[0].embedding
            logger.info(f"Successfully generated OpenAI embedding with {len(embedding)} dimensions")
            return embedding
            
        except AttributeError as e:
            logger.error(f"OpenAI client initialization or API error: {str(e)}")
            logger.error("This might be due to using an older version of the OpenAI library")
            logger.error("Check if you're using the v1.0.0+ of the library which requires different syntax")
            raise
            
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        # Fall back to mock embeddings in case of error
        logger.warning("Falling back to mock embeddings due to API error")
        return get_mock_embedding(text)
