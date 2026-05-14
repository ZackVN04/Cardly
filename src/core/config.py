from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URL: str
    MONGODB_DB_NAME: str = "Cardly"
    JWT_SECRET: str
    REFRESH_SECRET: str
    GCP_BUCKET: str = ""
    GCP_CREDENTIALS_JSON: str = ""
    GCS_PROJECT_ID: str = ""
    GCS_BUCKET_NAME: str = ""
    GCS_BASE_URL: str = "https://storage.googleapis.com"
    GEMINI_API_KEY: str = ""
    ENVIRONMENT: str = "dev"
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()