# Backend API

FastAPI backend for the stock charting web application.

## Setup

1. Install dependencies:
```bash
pip install -r ../requirements.txt
```

2. Ensure you have a `.env` file in the project root with database credentials:
```
DB_HOST=your-database-host
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
```

## Running the Server

### Development Mode
```bash
# From the project root
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Or directly:
```bash
python backend/main.py
```

### Production Mode
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
backend/
├── main.py              # FastAPI app entry point
├── api/                 # API route handlers
│   └── v1/              # API version 1 routes (to be created)
├── models/              # Pydantic models for request/response
├── db/                  # Database connection utilities
└── utils/               # Helper functions
```

## Development Notes

- The API uses CORS middleware to allow frontend connections
- Database connection utilities will be added in Phase 1.2
- API endpoints will be added in Phase 1.3

