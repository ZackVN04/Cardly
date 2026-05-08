from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URL: str
    JWT_SECRET: str
    REFRESH_SECRET: str
    GCP_BUCKET: str = ""
    GCP_CREDENTIALS_JSON: str = ""
    GEMINI_API_KEY: str = ""
    ENVIRONMENT: str = "dev"
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()
