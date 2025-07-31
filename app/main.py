import logging
import time
import uuid
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

from app.config import settings
from app.core.database import init_db, close_db
from app.api.routes import walls, trajectories, planning

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE) if os.path.exists(os.path.dirname(settings.LOG_FILE)) else logging.StreamHandler(),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Wall Finishing Robot Control System")
    try:
        await init_db()
        logger.info("Database initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        logger.info("Shutting down Wall Finishing Robot Control System")
        try:
            await close_db()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

# Create FastAPI application
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Advanced control system for wall-finishing robots with intelligent path planning and obstacle avoidance",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    request.state.request_id = request_id
    
    logger.info(f"Request {request_id}: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers.update({
            "X-Request-ID": request_id,
            "X-Process-Time": str(process_time)
        })
        logger.info(f"Response {request_id}: {response.status_code} ({process_time:.3f}s)")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request {request_id} failed after {process_time:.3f}s: {str(e)}")
        raise

def create_error_response(request: Request, status_code: int, error: str):
    """Create standardized error response"""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "status_code": status_code,
            "request_id": getattr(request.state, "request_id", "unknown"),
            "timestamp": time.time()
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    logger.error(f"HTTP Exception {getattr(request.state, 'request_id', 'unknown')}: {exc.status_code} - {exc.detail}")
    return create_error_response(request, exc.status_code, exc.detail)

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception {getattr(request.state, 'request_id', 'unknown')}: {str(exc)}", exc_info=True)
    return create_error_response(request, 500, "Internal server error")

# Include API routes
app.include_router(walls.router, prefix="/api/v1", tags=["walls"])
app.include_router(trajectories.router, prefix="/api/v1", tags=["trajectories"])
app.include_router(planning.router, prefix="/api/v1", tags=["planning"])

# Create static directory and mount static files
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main application page"""
    try:
        with open("app/static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Wall Finishing Robot Control System</title>
            <style>
                body{font-family:Arial,sans-serif;margin:40px;background:#f5f5f5}
                .container{background:white;padding:40px;border-radius:10px;max-width:800px;margin:0 auto}
                h1{color:#2c3e50}
                .info{background:#e8f4fd;padding:20px;border-radius:5px;margin:20px 0}
                .error{background:#f8d7da;color:#721c24;padding:20px;border-radius:5px;margin:20px 0}
                a{color:#3498db;text-decoration:none}
                a:hover{text-decoration:underline}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Wall Finishing Robot Control System</h1>
                <div class="error">
                    <strong>Frontend Missing:</strong> Please place <code>index.html</code> in <code>app/static/</code>
                </div>
                <div class="info">
                    <h3>🚀 System Status: Running</h3>
                    <p>
                        <a href="/docs">📚 API Documentation</a> | 
                        <a href="/health">💚 Health Check</a>
                    </p>
                </div>
            </div>
        </body>
        </html>""")

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.API_VERSION,
        "service": "Wall Finishing Robot Control System"
    }

if __name__ == "__main__":
    for directory in ["data/database", "logs"]:
        os.makedirs(directory, exist_ok=True)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )