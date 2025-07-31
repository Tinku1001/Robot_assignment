from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
import logging

from app.core.database import get_db
from app.models.database_models import Trajectory, TrajectoryPoint, Wall
from app.models.pydantic_models import TrajectoryResponse, TrajectoryPointResponse

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_trajectory_or_404(db: AsyncSession, trajectory_id: int, include_points: bool = False):
    """Get trajectory by ID or raise 404"""
    query = select(Trajectory).where(Trajectory.id == trajectory_id)
    if include_points:
        query = query.options(selectinload(Trajectory.points))
    
    trajectory = await db.scalar(query)
    if not trajectory:
        raise HTTPException(status_code=404, detail="Trajectory not found")
    return trajectory

def handle_error(operation: str, trajectory_id: int = None):
    """Handle errors with consistent logging and HTTP exceptions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                error_msg = f"Failed to {operation}"
                if trajectory_id:
                    error_msg += f" {trajectory_id}"
                logger.error(f"{error_msg}: {str(e)}")
                raise HTTPException(status_code=500, detail=error_msg)
        return wrapper
    return decorator

@router.get("/trajectories", response_model=List[TrajectoryResponse])
async def get_trajectories(wall_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                          algorithm: Optional[str] = Query(None), skip: int = Query(0, ge=0),
                          limit: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    """Get trajectories with optional filtering"""
    try:
        query = select(Trajectory)
        
        # Apply filters
        filters = []
        if wall_id:
            filters.append(Trajectory.wall_id == wall_id)
        if status:
            filters.append(Trajectory.status == status)
        if algorithm:
            filters.append(Trajectory.algorithm == algorithm)
        
        if filters:
            query = query.where(and_(*filters))
        
        trajectories = await db.scalars(query.offset(skip).limit(limit).order_by(desc(Trajectory.created_at)))
        result = trajectories.all()
        logger.info(f"Retrieved {len(result)} trajectories")
        return result
    except Exception as e:
        logger.error(f"Failed to get trajectories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trajectories")

@router.get("/trajectories/{trajectory_id}", response_model=TrajectoryResponse)
async def get_trajectory(trajectory_id: int, include_points: bool = Query(False), db: AsyncSession = Depends(get_db)):
    """Get a specific trajectory by ID"""
    try:
        trajectory = await get_trajectory_or_404(db, trajectory_id, include_points)
        if not include_points:
            trajectory.points = []
        return trajectory
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trajectory {trajectory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trajectory")

@router.get("/trajectories/{trajectory_id}/points")
async def get_trajectory_points(trajectory_id: int, start_sequence: int = Query(0, ge=0),
                               limit: int = Query(1000, ge=1, le=10000), db: AsyncSession = Depends(get_db)):
    """Get trajectory points with pagination - Returns format expected by frontend"""
    try:
        await get_trajectory_or_404(db, trajectory_id)  # Verify trajectory exists
        
        points = await db.scalars(select(TrajectoryPoint).where(
            and_(TrajectoryPoint.trajectory_id == trajectory_id, TrajectoryPoint.sequence_number >= start_sequence)
        ).order_by(TrajectoryPoint.sequence_number).limit(limit))
        
        points_data = [{"x": p.x, "y": p.y, "z": p.z, "tool_active": p.tool_active} for p in points]
        logger.info(f"Retrieved {len(points_data)} trajectory points for trajectory {trajectory_id}")
        return points_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trajectory points {trajectory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trajectory points")

@router.get("/trajectories/{trajectory_id}/points-detailed", response_model=List[TrajectoryPointResponse])
async def get_trajectory_points_detailed(trajectory_id: int, start_sequence: int = Query(0, ge=0),
                                        limit: int = Query(1000, ge=1, le=10000), db: AsyncSession = Depends(get_db)):
    """Get detailed trajectory points with all fields"""
    try:
        await get_trajectory_or_404(db, trajectory_id)  # Verify trajectory exists
        
        points = await db.scalars(select(TrajectoryPoint).where(
            and_(TrajectoryPoint.trajectory_id == trajectory_id, TrajectoryPoint.sequence_number >= start_sequence)
        ).order_by(TrajectoryPoint.sequence_number).limit(limit))
        
        result = points.all()
        logger.info(f"Retrieved {len(result)} detailed trajectory points for trajectory {trajectory_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get detailed trajectory points {trajectory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trajectory points")

@router.delete("/trajectories/{trajectory_id}")
async def delete_trajectory(trajectory_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a trajectory and all its points"""
    try:
        trajectory = await get_trajectory_or_404(db, trajectory_id)
        trajectory_name = trajectory.name or f"Trajectory {trajectory.id}"
        
        await db.delete(trajectory)
        await db.commit()
        logger.info(f"Deleted trajectory {trajectory_id}: {trajectory_name}")
        return {"message": "Trajectory deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete trajectory {trajectory_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete trajectory")

@router.get("/trajectories/{trajectory_id}/stats")
async def get_trajectory_stats(trajectory_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed statistics for a trajectory"""
    try:
        trajectory = await get_trajectory_or_404(db, trajectory_id)
        
        points = await db.scalars(select(TrajectoryPoint).where(
            TrajectoryPoint.trajectory_id == trajectory_id
        ).order_by(TrajectoryPoint.sequence_number))
        points_list = points.all()
        
        # Calculate statistics
        total_points = len(points_list)
        cutting_points = sum(1 for p in points_list if p.tool_active)
        rapid_points = total_points - cutting_points
        
        # Calculate path lengths
        total_length = cutting_length = rapid_length = 0.0
        for i in range(1, len(points_list)):
            prev, curr = points_list[i-1], points_list[i]
            distance = ((curr.x - prev.x)**2 + (curr.y - prev.y)**2 + (curr.z - prev.z)**2)**0.5
            total_length += distance
            if curr.tool_active:
                cutting_length += distance
            else:
                rapid_length += distance
        
        return {
            "trajectory_id": trajectory_id, "algorithm": trajectory.algorithm,
            "total_points": total_points, "cutting_points": cutting_points, "rapid_points": rapid_points,
            "total_length": total_length, "cutting_length": cutting_length, "rapid_length": rapid_length,
            "coverage_percentage": trajectory.coverage_percentage, "execution_time_ms": trajectory.execution_time_ms,
            "estimated_duration_minutes": trajectory.estimated_duration_minutes, "robot_width": trajectory.robot_width,
            "overlap_percentage": trajectory.overlap_percentage, "resolution": trajectory.resolution
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trajectory stats {trajectory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get trajectory statistics")