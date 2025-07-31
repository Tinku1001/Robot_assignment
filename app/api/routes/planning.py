# app/api/routes/planning.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import logging
import json

from app.core.database import get_db
from app.models.database_models import Wall
from app.models.pydantic_models import TrajectoryPlanRequest, PlanningResult, AlgorithmsResponse, AlgorithmInfo
from app.services.path_planning import PathPlanningService

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_wall_with_obstacles(db: AsyncSession, wall_id: int):
    """Get wall with obstacles or raise 404"""
    wall_query = select(Wall).where(Wall.id == wall_id).options(selectinload(Wall.obstacles))
    wall = await db.scalar(wall_query)
    if not wall:
        raise HTTPException(status_code=404, detail="Wall not found")
    return wall

async def handle_db_error(db: AsyncSession, operation: str, error: Exception):
    """Handle database errors with rollback"""
    logger.error(f"Failed to {operation}: {str(error)}", exc_info=True)
    try:
        await db.rollback()
    except Exception as rollback_error:
        logger.error(f"Error during rollback: {rollback_error}")
    raise HTTPException(status_code=500, detail=f"Failed to {operation}")

@router.post("/planning/plan", response_model=PlanningResult)
async def plan_trajectory(request: TrajectoryPlanRequest, db: AsyncSession = Depends(get_db)):
    """Plan a new trajectory for a wall"""
    try:
        algorithm = str(request.algorithm.value) if hasattr(request.algorithm, 'value') else str(request.algorithm)
        logger.info(f"Planning trajectory for wall {request.wall_id} with {algorithm} algorithm")
        
        wall = await get_wall_with_obstacles(db, request.wall_id)
        logger.info(f"Found wall '{wall.name}' ({wall.width}x{wall.height}m) with {len(wall.obstacles)} obstacles")
        
        # Plan trajectory
        try:
            planning_service = PathPlanningService()
            result = await planning_service.plan_trajectory(db, wall, request)
            
            if not isinstance(result, PlanningResult):
                logger.error(f"Planning service returned incorrect type: {type(result)}")
                raise HTTPException(status_code=500, detail="Internal error: Invalid response type from planning service")
            
            logger.info(f"Successfully planned trajectory {result.trajectory_id} for wall {request.wall_id}")
            logger.info(f"Metrics: {result.total_points} points, {result.total_length:.2f}m, {result.coverage_percentage:.1f}% coverage")
            return result
            
        except HTTPException:
            raise
        except Exception as planning_error:
            logger.error(f"Planning service error: {str(planning_error)}")
            await handle_db_error(db, "execute planning service", planning_error)
            
    except HTTPException:
        raise
    except Exception as e:
        await handle_db_error(db, "plan trajectory", e)
