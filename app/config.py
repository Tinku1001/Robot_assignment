from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/database/robot_control.db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0
    
    # API Configuration
    API_VERSION: str = "v1"
    API_TITLE: str = "Wall Finishing Robot Control System"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Environment
    DEBUG: bool = False
    TESTING: bool = False
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Performance
    MAX_TRAJECTORY_POINTS: int = 100000
    CACHE_TTL_SECONDS: int = 300
    REQUEST_TIMEOUT_SECONDS: int = 30
    
    # Path Planning
    ROBOT_WIDTH_CM: float = 10.0
    OVERLAP_PERCENTAGE: float = 20.0
    PATH_RESOLUTION_CM: float = 1.0
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    HEALTH_CHECK_INTERVAL: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()