import os
import uuid
import logging
from typing import List
from sqlalchemy.orm import Session
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

from ..models.models import File, Chunk, Embedding
from .vector_search import get_embedding

# Configure logging
logger = logging.getLogger("file_processing")

# Function to read text from a file
async def extract_text_from_file(file_path: str) -> str:
    """Extract text content from a file."""
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == '.txt':
        # For text files, read directly
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            return file.read()
    elif file_extension == '.pdf':
        # For PDF files, use PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
        except ImportError:
            # If PyPDF2 is not available, suggest installing it
            return "Error: PDF processing requires PyPDF2. Please install it with 'pip install PyPDF2'."
        except Exception as e:
            # Handle other potential errors
            return f"Error extracting text from PDF: {str(e)}"
    elif file_extension in ['.docx', '.doc']:
        # For Word documents, use python-docx
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except ImportError:
            # If python-docx is not available, suggest installing it
            return "Error: DOCX processing requires python-docx. Please install it with 'pip install python-docx'."
        except Exception as e:
            # Handle other potential errors
            return f"Error extracting text from DOCX: {str(e)}"
    else:
        # Unsupported file type
        return f"Error: Unsupported file type {file_extension}"

# Function to count tokens in text
def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")  # OpenAI's encoding for text-embedding-ada-002
    return len(encoding.encode(text))

# Function to chunk text into smaller segments
async def chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks of roughly equal token size.
    
    Args:
        text: The text to split into chunks
        chunk_size: Maximum number of tokens per chunk (default: 512 to match OpenAI's recommendation)
        chunk_overlap: Number of tokens of overlap between chunks (default: 50)
        
    Returns:
        List of text chunks
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=count_tokens,
    )
    return text_splitter.split_text(text)

# Function to process a file after upload
async def process_file(file_id: uuid.UUID, file_path: str, db: Session):
    """Process an uploaded file by extracting text, chunking it, and creating embeddings."""
    try:
        logger.info(f"Starting processing for file ID: {file_id}, path: {file_path}")
        
        # Update file status to processing
        db_file = db.query(File).filter(File.id == file_id).first()
        if not db_file:
            logger.error(f"File with ID {file_id} not found in database")
            return
        
        db_file.status = "Processing"
        db.commit()
        logger.info(f"Updated file status to 'Processing' for {db_file.filename}")
        
        # Delete existing chunks and embeddings (if any) to avoid issues when reprocessing
        # First get all chunk IDs for this file
        chunk_ids = [chunk_id for (chunk_id,) in db.query(Chunk.id).filter(Chunk.file_id == file_id).all()]
        
        # Delete embeddings associated with these chunks
        if chunk_ids:
            logger.info(f"Found {len(chunk_ids)} existing chunks with potential embeddings to delete")
            deletion_count = db.query(Embedding).filter(Embedding.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
            logger.info(f"Deleted {deletion_count} existing embeddings for file {file_id}")
        
        # Now it's safe to delete the chunks
        logger.info(f"Deleting existing chunks for file {file_id}")
        db.query(Chunk).filter(Chunk.file_id == file_id).delete()
        
        # Extract text from file
        logger.info(f"Extracting text from {file_path}")
        text = await extract_text_from_file(file_path)
        
        if text.startswith("Error:"):
            db_file.status = "Error"
            db.commit()
            logger.error(f"Error extracting text from file {file_path}: {text}")
            return
        
        logger.info(f"Successfully extracted text: {len(text)} characters")
        
        # Chunk the text
        logger.info("Chunking text content")
        chunks = await chunk_text(text)
        logger.info(f"Text split into {len(chunks)} chunks")
        
        # Clear existing chunks for this file if any (for reprocessing)
        chunk_count = db.query(Chunk).filter(Chunk.file_id == file_id).count()
        if chunk_count > 0:
            logger.info(f"Deleting {chunk_count} existing chunks for file ID {file_id}")
            db.query(Chunk).filter(Chunk.file_id == file_id).delete()
            db.commit()
        
        # Save chunks to database
        successful_embeddings = 0
        failed_embeddings = 0
        
        logger.info(f"Processing {len(chunks)} chunks for embedding")
        for i, chunk_content in enumerate(chunks):
            token_count = count_tokens(chunk_content)
            logger.info(f"Processing chunk {i+1}/{len(chunks)}, tokens: {token_count}")
            
            # Create chunk
            chunk = Chunk(
                id=uuid.uuid4(),
                chunk_number=i + 1,
                text=chunk_content,
                token_count=token_count,
                file_id=file_id
            )
            db.add(chunk)
            db.flush()  # Flush to get the ID without committing
            
            # Generate embedding for the chunk
            logger.info(f"Generating embedding for chunk {i+1}")
            try:
                embedding_vector = await get_embedding(chunk_content)
                if embedding_vector:
                    logger.info(f"Embedding generated successfully with {len(embedding_vector)} dimensions")
                    embedding = Embedding(
                        id=uuid.uuid4(),
                        chunk_id=chunk.id,
                        embedding_vector=embedding_vector,
                        embedding_model="text-embedding-ada-002"
                    )
                    db.add(embedding)
                    successful_embeddings += 1
                else:
                    logger.warning(f"Failed to generate embedding for chunk {i+1} - returned None")
                    failed_embeddings += 1
            except Exception as e:
                logger.error(f"Error generating embedding for chunk {i+1}: {str(e)}")
                failed_embeddings += 1
        
        # Commit all changes
        db.commit()
        logger.info(f"Chunk processing complete. Successful embeddings: {successful_embeddings}, Failed: {failed_embeddings}")
        
        # Update file status to embedded
        db_file.status = "Embedded"
        db.commit()
        logger.info(f"Successfully processed file {file_path}, status updated to 'Embedded'")
        
    except Exception as e:
        # Update file status to error
        logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)
        db_file = db.query(File).filter(File.id == file_id).first()
        if db_file:
            db_file.status = "Error"
            db.commit()
            logger.info(f"Updated file status to 'Error' due to exception")

# Function to reprocess an existing file
async def re_process_file(file_id: uuid.UUID, file_path: str, db: Session):
    """Reprocess an existing file by deleting its chunks and embeddings and processing it again."""
    try:
        logger.info(f"Starting reprocessing for file ID: {file_id}, path: {file_path}")
        
        # Check if file exists
        db_file = db.query(File).filter(File.id == file_id).first()
        if not db_file:
            logger.error(f"File with ID {file_id} not found")
            return
            
        logger.info(f"Reprocessing file: {db_file.filename}")
        
        # First get all chunk IDs for this file
        chunk_ids = [chunk_id for (chunk_id,) in db.query(Chunk.id).filter(Chunk.file_id == file_id).all()]
        
        # Delete embeddings associated with these chunks
        if chunk_ids:
            logger.info(f"Found {len(chunk_ids)} chunks with potential embeddings to delete")
            deletion_count = db.query(Embedding).filter(Embedding.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
            logger.info(f"Deleted {deletion_count} embeddings for file {file_id}")
        
        # Now it's safe to delete the chunks
        logger.info(f"Deleting existing chunks for file {file_id}")
        db.query(Chunk).filter(Chunk.file_id == file_id).delete()
        db.commit()
        
        # Process the file again
        logger.info(f"Starting fresh processing for file ID {file_id}")
        await process_file(file_id, file_path, db)
        
    except Exception as e:
        # Update file status to error
        logger.error(f"Error reprocessing file {file_path}: {str(e)}", exc_info=True)
        db_file = db.query(File).filter(File.id == file_id).first()
        if db_file:
            db_file.status = "Error"
            db.commit()
            logger.info(f"Updated file status to 'Error' due to exception")
