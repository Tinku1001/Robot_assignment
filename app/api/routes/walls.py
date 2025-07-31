# app/api/routes/walls.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import logging
import json

from app.core.database import get_db
from app.models.database_models import Wall, Obstacle
from app.models.pydantic_models import (
    WallCreate, WallResponse, WallUpdate, ObstacleCreate, ObstacleResponse, ErrorResponse
)
from app.utils.geometry import GeometryUtils

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_wall_or_404(db: AsyncSession, wall_id: int, include_obstacles: bool = False):
    """Get wall by ID or raise 404"""
    query = select(Wall).where(Wall.id == wall_id)
    if include_obstacles:
        query = query.options(selectinload(Wall.obstacles))
    
    wall = await db.scalar(query)
    if not wall:
        raise HTTPException(status_code=404, detail="Wall not found")
    return wall

def create_obstacle_response(obstacle):
    """Convert obstacle to response format"""
    obstacle_dict = obstacle.__dict__.copy()
    obstacle_dict["geometry_data"] = json.loads(obstacle.geometry_data)
    return ObstacleResponse(**obstacle_dict)

def create_wall_response(wall):
    """Convert wall to response format with obstacles"""
    obstacles = [create_obstacle_response(obs) for obs in wall.obstacles]
    wall_dict = wall.__dict__.copy()
    wall_dict["obstacles"] = obstacles
    return WallResponse(**wall_dict)

async def handle_db_error(db: AsyncSession, operation: str, error: Exception, item_id: int = None):
    """Handle database errors with rollback"""
    logger.error(f"Failed to {operation}{f' {item_id}' if item_id else ''}: {str(error)}")
    await db.rollback()
    raise HTTPException(status_code=500, detail=f"Failed to {operation}")

def calculate_obstacle_bounds(obstacle_type: str, geometry_data: dict):
    """Calculate bounding box for obstacle"""
    if obstacle_type == "rectangle":
        center_x, center_y = geometry_data["center_x"], geometry_data["center_y"]
        width, height = geometry_data["width"], geometry_data["height"]
        return GeometryUtils.rectangle_bounds(center_x, center_y, width, height)
    elif obstacle_type == "circle":
        center_x, center_y = geometry_data["center_x"], geometry_data["center_y"]
        radius = geometry_data["radius"]
        return center_x - radius, center_y - radius, center_x + radius, center_y + radius
    return 0, 0, 0, 0

@router.post("/walls", response_model=WallResponse, status_code=201)
async def create_wall(wall_data: WallCreate, db: AsyncSession = Depends(get_db)):
    """Create a new wall"""
    try:
        logger.info(f"Creating wall: {wall_data.name} ({wall_data.width}x{wall_data.height}m)")
        
        wall = Wall(name=wall_data.name, width=wall_data.width, height=wall_data.height,
                   origin_x=wall_data.origin_x, origin_y=wall_data.origin_y)
        db.add(wall)
        await db.commit()
        await db.refresh(wall)

        # Load with obstacles (empty on creation)
        wall = await get_wall_or_404(db, wall.id, include_obstacles=True)
        logger.info(f"Created wall {wall.id}: {wall.name}")
        return create_wall_response(wall)
    except Exception as e:
        await handle_db_error(db, "create wall", e)

@router.get("/walls", response_model=List[WallResponse])
async def get_walls(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                   search: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    """Get all walls with optional search and pagination"""
    try:
        query = select(Wall).options(selectinload(Wall.obstacles))
        if search:
            query = query.where(Wall.name.ilike(f"%{search}%"))
        
        walls = await db.scalars(query.offset(skip).limit(limit).order_by(Wall.created_at.desc()))
        return [create_wall_response(wall) for wall in walls.all()]
    except Exception as e:
        logger.error(f"Failed to get walls: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve walls")

@router.get("/walls/{wall_id}", response_model=WallResponse)
async def get_wall(wall_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific wall by ID"""
    try:
        wall = await get_wall_or_404(db, wall_id, include_obstacles=True)
        return create_wall_response(wall)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get wall {wall_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve wall")

@router.put("/walls/{wall_id}", response_model=WallResponse)
async def update_wall(wall_id: int, wall_data: WallUpdate, db: AsyncSession = Depends(get_db)):
    """Update a wall"""
    try:
        wall = await get_wall_or_404(db, wall_id)
        
        # Update fields if provided
        update_fields = ["name", "width", "height", "origin_x", "origin_y"]
        for field in update_fields:
            value = getattr(wall_data, field)
            if value is not None:
                setattr(wall, field, value)
        
        await db.commit()
        await db.refresh(wall)
        logger.info(f"Updated wall {wall.id}: {wall.name}")
        return wall
    except HTTPException:
        raise
    except Exception as e:
        await handle_db_error(db, "update wall", e, wall_id)

@router.delete("/walls/{wall_id}")
async def delete_wall(wall_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a wall and all its associated data"""
    try:
        wall = await get_wall_or_404(db, wall_id)
        wall_name = wall.name
        await db.delete(wall)
        await db.commit()
        logger.info(f"Deleted wall {wall_id}: {wall_name}")
        return {"message": "Wall deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await handle_db_error(db, "delete wall", e, wall_id)

@router.post("/walls/{wall_id}/obstacles", response_model=ObstacleResponse, status_code=201)
async def create_obstacle(wall_id: int, obstacle_data: ObstacleCreate, db: AsyncSession = Depends(get_db)):
    """Add an obstacle to a wall"""
    try:
        wall = await get_wall_or_404(db, wall_id)  # Verify wall exists
        geometry_data = obstacle_data.geometry_data
        
        # Validate obstacle geometry
        if not GeometryUtils.validate_obstacle_geometry(obstacle_data.obstacle_type, geometry_data, wall.width, wall.height):
            raise HTTPException(status_code=400, detail="Invalid obstacle geometry")
        
        # Calculate bounding box
        min_x, min_y, max_x, max_y = calculate_obstacle_bounds(obstacle_data.obstacle_type, geometry_data)
        
        obstacle = Obstacle(wall_id=wall_id, name=obstacle_data.name, obstacle_type=obstacle_data.obstacle_type,
                           geometry_data=json.dumps(geometry_data), min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)
        db.add(obstacle)
        await db.commit()
        await db.refresh(obstacle)
        
        logger.info(f"Created obstacle {obstacle.id} on wall {wall_id}: {obstacle.name}")
        return create_obstacle_response(obstacle)
    except HTTPException:
        raise
    except Exception as e:
        await handle_db_error(db, "create obstacle", e, wall_id)

@router.get("/walls/{wall_id}/obstacles", response_model=List[ObstacleResponse])
async def get_wall_obstacles(wall_id: int, db: AsyncSession = Depends(get_db)):
    """Get all obstacles for a wall"""
    try:
        await get_wall_or_404(db, wall_id)  # Verify wall exists
        obstacles = await db.scalars(select(Obstacle).where(Obstacle.wall_id == wall_id))
        return [create_obstacle_response(obstacle) for obstacle in obstacles.all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get obstacles for wall {wall_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve obstacles")

@router.delete("/walls/{wall_id}/obstacles/{obstacle_id}")
async def delete_obstacle(wall_id: int, obstacle_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an obstacle"""
    try:
        obstacle = await db.scalar(select(Obstacle).where(and_(Obstacle.id == obstacle_id, Obstacle.wall_id == wall_id)))
        if not obstacle:
            raise HTTPException(status_code=404, detail="Obstacle not found")
        
        obstacle_name = obstacle.name
        await db.delete(obstacle)
        await db.commit()
        logger.info(f"Deleted obstacle {obstacle_id} from wall {wall_id}: {obstacle_name}")
        return {"message": "Obstacle deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await handle_db_error(db, "delete obstacle", e, obstacle_id)