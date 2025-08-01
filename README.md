# SAP FICO Uploader - Backend API

FastAPI backend for the SAP FICO Vector Uploader application.

## Features

- **User Authentication**: JWT-based authentication with admin roles
- **File Processing**: Upload and chunk PDF/text documents
- **Vector Search**: OpenAI embeddings with similarity search
- **Admin Management**: Complete user management system
- **Database**: PostgreSQL with SQLAlchemy ORM

## Quick Start

1. Install dependencies:
   \\\ash
   pip install -r requirements.txt
   \\\

2. Set up environment variables:
   \\\ash
   cp .env.example .env
   # Edit .env with your values
   \\\

3. Run the server:
   \\\ash
   python run.py
   \\\

## Environment Variables

- \DATABASE_URL\: PostgreSQL connection string
- \SECRET_KEY\: JWT secret key
- \OPENAI_API_KEY\: OpenAI API key for embeddings
- \ALGORITHM\: JWT algorithm (default: HS256)
- \ACCESS_TOKEN_EXPIRE_MINUTES\: Token expiration (default: 30)

## API Endpoints

- \/auth/*\: Authentication endpoints
- \/admin/*\: Admin user management
- \/files/*\: File upload and management
- \/chunks/*\: Document chunks
- \/search/*\: Vector search

## Deployment

See deployment configurations:
- \Dockerfile\: Docker containerization
- \ailway.toml\: Railway deployment
- \ender.yaml\: Render deployment

## Development

- Create admin user: \python create_admin_user.py\
- Test database: \python test_db_connection.py\

