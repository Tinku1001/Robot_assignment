import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy import create_engine, event, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
import os

logger = logging.getLogger(__name__)

# Create data directories
for directory in ["data/database", "logs"]:
    os.makedirs(directory, exist_ok=True)

# Create async engine with optimized settings for SQLite
engine = create_async_engine(settings.DATABASE_URL, poolclass=StaticPool, pool_pre_ping=True,
                           pool_recycle=300, echo=settings.DEBUG, 
                           connect_args={"check_same_thread": False, "timeout": 30})

# Session factory
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False,
                                     autoflush=False, autocommit=False)

Base = declarative_base()
metadata = MetaData()

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Optimize SQLite for performance and concurrency"""
    cursor = dbapi_connection.cursor()
    try:
        # Execute all pragma settings at once
        pragmas = [
            "PRAGMA journal_mode=WAL",      # Write-Ahead Logging
            "PRAGMA synchronous=NORMAL",    # Faster writes
            "PRAGMA cache_size=-64000",     # 64MB cache
            "PRAGMA temp_store=MEMORY",     # Use memory for temp
            "PRAGMA mmap_size=268435456",   # 256MB memory map
            "PRAGMA optimize",              # Query planner optimization
            "PRAGMA analysis_limit=1000",   # Better statistics
            "PRAGMA busy_timeout=30000"     # 30 second timeout
        ]
        for pragma in pragmas:
            cursor.execute(pragma)
        logger.info("SQLite pragmas configured successfully")
    except Exception as e:
        logger.error(f"Failed to set SQLite pragmas: {e}")
    finally:
        cursor.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

async def run_migrations():
    """Run database migration to add missing columns"""
    try:
        async with engine.begin() as conn:
            logger.info("Running database migrations...")
            
            # Check if total_points column exists in trajectories table
            result = await conn.execute(text("PRAGMA table_info(trajectories);"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'total_points' not in columns:
                logger.info("Adding missing total_points column to trajectories table...")
                await conn.execute(text("ALTER TABLE trajectories ADD COLUMN total_points INTEGER DEFAULT 0;"))
                logger.info("✅ total_points column added successfully!")
            else:
                logger.info("✅ total_points column already exists")
            
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise

async def create_indexes(conn):
    """Create all database indexes for optimization"""
    indexes = [
        ("idx_trajectory_points_spatial", "trajectory_points(x, y)"),
        ("idx_obstacles_spatial", "obstacles(min_x, min_y, max_x, max_y)"),
        ("idx_walls_dimensions", "walls(width, height)"),
        ("idx_trajectories_status", "trajectories(status, created_at)"),
        ("idx_trajectories_wall", "trajectories(wall_id)"),
        ("idx_trajectory_points_trajectory", "trajectory_points(trajectory_id, sequence_number)")
    ]
    
    for index_name, index_def in indexes:
        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def};"))

async def init_db():
    """Initialize database with tables and indexes"""
    try:
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Create spatial indexes for geometric queries
            await create_indexes(conn)
            
            # Analyze tables for query optimization
            await conn.execute(text("ANALYZE"))
        
        logger.info("Database initialized successfully with optimized indexes")
        
        # Run migrations after table creation
        await run_migrations()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def close_db():
    """Close database connections"""
    await engine.dispose()
    logger.info("Database connections closed")

async def migrate_now():
    """Manual migration function - call this if needed"""
    await run_migrations()

if __name__ == "__main__":
    # Allow running migrations directly
    asyncio.run(migrate_now())