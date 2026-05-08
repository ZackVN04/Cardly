# Cardly — Backend API

AI-powered business card scanner & smart contact management.

## Stack

- Python 3.11+ / FastAPI / Pydantic v2
- MongoDB Atlas / Motor (async)
- JWT Auth (access token + HttpOnly refresh cookie)
- Google Cloud Storage, Gemini API

## Setup

```bash
cp .env.example .env
# fill in .env values

pip install -r requirements/dev.txt
uvicorn src.main:app --reload
```

## Testing

```bash
pytest
```
