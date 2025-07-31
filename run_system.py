"""
Complete startup script for Wall Finishing Robot Control System
Handles all setup, initialization, and startup automatically
"""

import os
import sys
import asyncio
import subprocess
import time
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.resolve()))

def setup_logging():
    """Setup basic logging for startup script"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

def print_banner():
    """Print startup banner"""
    print("=" * 60)
    print("🤖 WALL FINISHING ROBOT CONTROL SYSTEM")
    print("🔧 Production-Ready Path Planning & Visualization")
    print("📊 SQLite Database with Advanced Optimization")
    print("🎯 Complete Sample Case: 5m×5m Wall + 25cm×25cm Window")
    print("=" * 60)

def check_python_and_setup():
    """Check Python version and setup directories"""
    logger = logging.getLogger(__name__)
    
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8+ required. Current version: %s", sys.version)
        return False
    
    logger.info("✅ Python version: %s", sys.version.split()[0])
    
    # Create directories
    for dir_path in ["data/database", "data/exports", "logs", "app/static"]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    logger.info("✅ Directories created")
    
    return True

def check_and_install_dependencies():
    """Check if required packages are installed and install if missing"""
    logger = logging.getLogger(__name__)
    
    required_packages = ['fastapi', 'uvicorn', 'sqlalchemy', 'aiosqlite', 
                        'pydantic', 'pydantic-settings', 'numpy', 'shapely', 'psutil']
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.info("📦 Installing missing dependencies...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                         check=True, capture_output=True, text=True)
            logger.info("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            logger.error("❌ Failed to install dependencies: %s", e.stderr)
            return False
    else:
        logger.info("✅ All dependencies already installed")
    
    return True

async def initialize_database():
    """Initialize the SQLite database"""
    logger = logging.getLogger(__name__)
    try:
        from app.core.database import init_db
        logger.info("🗄️  Initializing SQLite database...")
        await init_db()
        logger.info("✅ Database initialized with optimized indexes")
        return True
    except Exception as e:
        logger.error("❌ Database initialization failed: %s", e)
        return False

def check_files_and_create_env():
    """Check HTML file and create .env file if needed"""
    logger = logging.getLogger(__name__)
    
    # Check HTML file
    if Path("app/static/index.html").exists():
        logger.info("✅ Frontend HTML file found")
    else:
        logger.warning("⚠️  Frontend HTML file not found - place index.html in app/static/")
    
    # Create .env file if needed
    env_path = Path(".env")
    if not env_path.exists():
        logger.info("📝 Creating .env configuration file...")
        env_content = """# Wall Finishing Robot Control System Configuration
DATABASE_URL=sqlite+aiosqlite:///./data/database/robot_control.db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=0
API_VERSION=v1
API_TITLE=Wall Finishing Robot Control System
SECRET_KEY=production-secret-key-change-this
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=true
TESTING=false
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
MAX_TRAJECTORY_POINTS=100000
CACHE_TTL_SECONDS=300
REQUEST_TIMEOUT_SECONDS=30
ROBOT_WIDTH_CM=10.0
OVERLAP_PERCENTAGE=20.0
PATH_RESOLUTION_CM=1.0
ENABLE_METRICS=true
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30
"""
        with open(env_path, 'w') as f:
            f.write(env_content)
        logger.info("✅ .env file created with default configuration")
    else:
        logger.info("✅ .env file already exists")

def start_server():
    """Start the FastAPI server"""
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Wall Finishing Robot Control System...")
    print("\n" + "=" * 50)
    print("🌐 SYSTEM READY!")
    print("=" * 50)
    print("📍 Web Interface:     http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("📊 System Status:     http://localhost:8000/api/v1/monitoring/system-status")
    print("🏥 Health Check:      http://localhost:8000/health")
    print("=" * 50)
    print("⏹️  Press Ctrl+C to stop the server\n")
    
    try:
        subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload", 
                       "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"])
    except KeyboardInterrupt:
        print("\n👋 Shutting down system...")
        logger.info("System shut down by user")

def main():
    """Main startup function"""
    logger = setup_logging()
    print_banner()
    
    # Check Python version and setup directories
    if not check_python_and_setup():
        sys.exit(1)
    
    # Create .env and check files
    check_files_and_create_env()
    
    # Check and install dependencies
    if not check_and_install_dependencies():
        logger.error("❌ Dependency installation failed")
        sys.exit(1)
    
    # Initialize database
    try:
        asyncio.run(initialize_database())
    except Exception as e:
        logger.error("❌ Database initialization failed: %s", e)
        sys.exit(1)
    
    # Start server
    start_server()

if __name__ == "__main__":
    main()