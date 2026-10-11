"""Application configuration using pydantic-settings"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database
    DATABASE_URL: str = "sqlite:///./razryad.db"
    
    # Security
    JWT_SECRET: str = "CHANGE-ME-IN-PRODUCTION-USE-STRONG-RANDOM-KEY"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL: int = 3600  # seconds (1 hour)
    JWT_REFRESH_TTL: int = 2592000  # seconds (30 days)
    
    # Email confirmation
    EMAIL_CONFIRM_TTL: int = 86400  # seconds (24 hours)
    
    # Development mode
    DEV_MODE: bool = True
    
    # LLM features (item generation, calibration)
    LLM_ENABLED: bool = False
    LLM_API_KEY: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    # Grade change cooldown (days)
    GRADE_CHANGE_COOLDOWN_JUNIOR: int = 30
    GRADE_CHANGE_COOLDOWN_MIDDLE_PLUS: int = 90
    
    # Assessment
    CAT_MIN_ITEMS: int = 12
    CAT_MAX_ITEMS: int = 18
    CAT_TIME_LIMIT: int = 2700  # seconds (45 minutes)
    CAT_SE_THRESHOLD: float = 0.35
    
    # Matching
    FRESHNESS_DECAY_DAYS: int = 45
    
    # Rate limiting
    INVITATION_DAILY_LIMIT: int = 20
    INVITATION_WEEKLY_LIMIT: int = 100
    
    # S3 / MinIO (optional)
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "razryad"
    
    # Redis (optional, for caching and queue)
    REDIS_URL: str = ""
    
    # Application
    APP_TITLE: str = "РАЗРЯД API"
    APP_DESCRIPTION: str = "Платформа обратного подбора ИТ-специалистов с подтверждённым грейдом"
    APP_VERSION: str = "0.1.0"
    

settings = Settings()
