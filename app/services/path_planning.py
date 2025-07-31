import numpy as np
import logging
import json
import time
import math
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from app.models.database_models import Wall, Obstacle, Trajectory, TrajectoryPoint
from app.models.pydantic_models import TrajectoryPlanRequest, PlanningResult
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

@dataclass
class PathPoint:
    x: float
    y: float
    z: float = 0.0
    orientation: float = 0.0
    tool_active: bool = True
    motion_type: str = "linear"
    feed_rate: float = 100.0

@dataclass
class PlanningParameters:
    robot_width: float
    overlap_percentage: float
    resolution: float
    wall_width: float
    wall_height: float
    obstacles: List[Dict[str, Any]]

class PathPlanningService:
    RAPID_THRESHOLD = 0.05  # 5cm
    AVG_FEED_RATE = 0.1  # m/min
    COLLINEAR_TOLERANCE = 0.001
    BATCH_SIZE = 1000
    
    def __init__(self):
        pass
    
    async def plan_trajectory(self, db: AsyncSession, wall: Wall, request: TrajectoryPlanRequest) -> PlanningResult:
        """Main entry point for trajectory planning"""
        start_time = time.time()
        
        try:
            algorithm = self._get_algorithm_name(request.algorithm)
            logger.info(f"Starting trajectory planning for wall {wall.id} with {algorithm} algorithm")
            
            params = self._prepare_planning_parameters(wall, request)
            path_points = self._execute_algorithm(algorithm, params)
            optimized_points = self._optimize_path(path_points, params)
            metrics = self._calculate_path_metrics(optimized_points, params)
            
            trajectory = await self._create_trajectory_record(db, wall, request, optimized_points, metrics, start_time)
            execution_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"Trajectory planning completed: {len(optimized_points)} points, {metrics['total_length']:.2f}m path")
            
            return PlanningResult(
                trajectory_id=trajectory.id,
                wall_id=wall.id,
                algorithm=algorithm,
                total_points=len(optimized_points),
                total_length=metrics['total_length'],
                coverage_percentage=metrics['coverage_percentage'],
                execution_time_ms=execution_time,
                estimated_duration_minutes=metrics['estimated_duration'],
                status=trajectory.status
            )
            
        except Exception as e:
            logger.error(f"Path planning failed: {str(e)}")
            await db.rollback()
            raise
    
    def _get_algorithm_name(self, algorithm) -> str:
        """Extract algorithm name from enum or string"""
        return str(algorithm.value) if hasattr(algorithm, 'value') else str(algorithm)
    
    def _prepare_planning_parameters(self, wall: Wall, request: TrajectoryPlanRequest) -> PlanningParameters:
        """Prepare parameters for path planning"""
        obstacles_data = []
        for obstacle in wall.obstacles:
            geometry_data = json.loads(obstacle.geometry_data) if isinstance(obstacle.geometry_data, str) else obstacle.geometry_data
            obstacles_data.append({
                'type': obstacle.obstacle_type,
                'geometry': geometry_data,
                'bounds': {'min_x': obstacle.min_x, 'min_y': obstacle.min_y, 'max_x': obstacle.max_x, 'max_y': obstacle.max_y}
            })
        
        logger.info(f"Planning for wall {wall.width}x{wall.height}m with {len(obstacles_data)} obstacles")
        
        return PlanningParameters(
            robot_width=request.robot_width,
            overlap_percentage=request.overlap_percentage,
            resolution=request.resolution,
            wall_width=wall.width,
            wall_height=wall.height,
            obstacles=obstacles_data
        )
    
    def _execute_algorithm(self, algorithm: str, params: PlanningParameters) -> List[PathPoint]:
        """Execute the specified planning algorithm"""
        algorithms = {
            "boustrophedon": self._plan_boustrophedon,
            "spiral": self._plan_spiral,
            "zigzag": self._plan_zigzag
        }
        
        if algorithm not in algorithms:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        
        return algorithms[algorithm](params)
    
    def _plan_boustrophedon(self, params: PlanningParameters) -> List[PathPoint]:
        """Implement boustrophedon (back-and-forth) coverage pattern"""
        logger.info("Planning boustrophedon trajectory")
        
        path_points = []
        effective_width = params.robot_width * (1 - params.overlap_percentage / 100)
        y_positions = np.arange(params.robot_width/2, params.wall_height - params.robot_width/2, effective_width)
        
        direction = 1
        for y in y_positions:
            x_start = params.robot_width/2 if direction == 1 else params.wall_width - params.robot_width/2
            x_end = params.wall_width - params.robot_width/2 if direction == 1 else params.robot_width/2
            x_positions = np.arange(x_start, x_end, params.resolution * direction)
            
            for x in x_positions:
                if self._is_point_free(x, y, params):
                    path_points.append(PathPoint(
                        x=float(x), y=float(y),
                        orientation=0 if direction == 1 else math.pi
                    ))
            
            direction *= -1
        
        logger.info(f"Generated {len(path_points)} points for boustrophedon trajectory")
        return path_points
    
    def _plan_spiral(self, params: PlanningParameters) -> List[PathPoint]:
        """Implement spiral coverage pattern"""
        logger.info("Planning spiral trajectory")
        
        path_points = []
        center_x, center_y = params.wall_width / 2, params.wall_height / 2
        max_radius = min(params.wall_width, params.wall_height) / 2 - params.robot_width / 2
        effective_width = params.robot_width * (1 - params.overlap_percentage / 100)
        
        radius, angle = params.robot_width / 2, 0
        
        while radius < max_radius:
            angle_step = params.resolution / max(radius, 0.01)
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            if self._is_within_bounds(x, y, params) and self._is_point_free(x, y, params):
                path_points.append(PathPoint(x=x, y=y, orientation=angle + math.pi/2))
            
            angle += angle_step
            if angle >= 2 * math.pi:
                angle = 0
                radius += effective_width
        
        logger.info(f"Generated {len(path_points)} points for spiral trajectory")
        return path_points
    
    def _plan_zigzag(self, params: PlanningParameters) -> List[PathPoint]:
        """Implement zigzag coverage pattern"""
        logger.info("Planning zigzag trajectory")
        
        path_points = []
        diagonal_angle = math.pi / 4
        effective_width = params.robot_width * (1 - params.overlap_percentage / 100)
        spacing = effective_width / math.sin(diagonal_angle)
        num_passes = int(params.wall_width / spacing) + 1
        
        for i in range(num_passes):
            x_offset = i * spacing
            
            if i % 2 == 0:  # Bottom-left to top-right
                start_x, start_y = x_offset, params.robot_width / 2
                end_x = min(params.wall_width - params.robot_width/2, x_offset + params.wall_height)
                end_y = min(params.wall_height - params.robot_width/2, start_y + (end_x - start_x))
                orientation = diagonal_angle
            else:  # Top-left to bottom-right
                start_x, start_y = x_offset, params.wall_height - params.robot_width/2
                end_x = min(params.wall_width - params.robot_width/2, x_offset + params.wall_height)
                end_y = max(params.robot_width/2, start_y - (end_x - start_x))
                orientation = -diagonal_angle
            
            distance = self._calculate_distance(start_x, start_y, end_x, end_y)
            num_points = max(2, int(distance / params.resolution))
            
            for j in range(num_points):
                t = j / max(num_points - 1, 1)
                x = start_x + t * (end_x - start_x)
                y = start_y + t * (end_y - start_y)
                
                if self._is_point_free(x, y, params):
                    path_points.append(PathPoint(x=x, y=y, orientation=orientation))
        
        logger.info(f"Generated {len(path_points)} points for zigzag trajectory")
        return path_points
    
    def _is_within_bounds(self, x: float, y: float, params: PlanningParameters) -> bool:
        """Check if point is within wall bounds"""
        return (params.robot_width/2 <= x <= params.wall_width - params.robot_width/2 and 
                params.robot_width/2 <= y <= params.wall_height - params.robot_width/2)
    
    def _is_point_free(self, x: float, y: float, params: PlanningParameters) -> bool:
        """Check if a point is free from obstacles"""
        buffer = params.robot_width / 2
        for obstacle in params.obstacles:
            if obstacle['type'] == 'rectangle':
                geom = obstacle['geometry']
                if (geom['center_x'] - geom['width']/2 - buffer <= x <= geom['center_x'] + geom['width']/2 + buffer and
                    geom['center_y'] - geom['height']/2 - buffer <= y <= geom['center_y'] + geom['height']/2 + buffer):
                    return False
        return True
    
    def _calculate_distance(self, x1: float, y1: float, x2: float, y2: float, z1: float = 0, z2: float = 0) -> float:
        """Calculate distance between two points"""
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
    
    def _optimize_path(self, path_points: List[PathPoint], params: PlanningParameters) -> List[PathPoint]:
        """Optimize path for efficiency"""
        if len(path_points) < 2:
            return path_points
        
        # Remove collinear points
        optimized = [path_points[0]]
        for i in range(1, len(path_points) - 1):
            if not self._is_collinear(path_points[i-1], path_points[i], path_points[i+1]):
                optimized.append(path_points[i])
        
        if len(path_points) > 1:
            optimized.append(path_points[-1])
        
        return self._add_connecting_moves(optimized)
    
    def _is_collinear(self, p1: PathPoint, p2: PathPoint, p3: PathPoint) -> bool:
        """Check if three points are collinear"""
        cross_product = abs((p2.x - p1.x) * (p3.y - p1.y) - (p2.y - p1.y) * (p3.x - p1.x))
        return cross_product < self.COLLINEAR_TOLERANCE
    
    def _add_connecting_moves(self, path_points: List[PathPoint]) -> List[PathPoint]:
        """Add connecting moves between path segments"""
        if len(path_points) < 2:
            return path_points
        
        optimized_points = [path_points[0]]
        
        for i in range(1, len(path_points)):
            prev_point = path_points[i-1]
            current_point = path_points[i]
            
            distance = self._calculate_distance(prev_point.x, prev_point.y, current_point.x, current_point.y)
            
            if distance > self.RAPID_THRESHOLD:
                optimized_points.append(PathPoint(
                    x=current_point.x, y=current_point.y, z=0.0,
                    tool_active=False, motion_type="rapid"
                ))
            
            optimized_points.append(current_point)
        
        return optimized_points
    
    def _calculate_path_metrics(self, path_points: List[PathPoint], params: PlanningParameters) -> Dict[str, float]:
        """Calculate path performance metrics"""
        if not path_points:
            return {'total_length': 0.0, 'coverage_percentage': 0.0, 'estimated_duration': 0.0}
        
        total_length = cutting_length = 0.0
        
        for i in range(1, len(path_points)):
            segment_length = self._calculate_distance(
                path_points[i-1].x, path_points[i-1].y,
                path_points[i].x, path_points[i].y,
                path_points[i-1].z, path_points[i].z
            )
            total_length += segment_length
            if path_points[i].tool_active:
                cutting_length += segment_length
        
        # Calculate coverage
        wall_area = params.wall_width * params.wall_height
        obstacle_area = sum(obs['geometry']['width'] * obs['geometry']['height'] 
                          for obs in params.obstacles if obs['type'] == 'rectangle')
        
        effective_area = wall_area - obstacle_area
        covered_area = cutting_length * params.robot_width
        coverage_percentage = min(100.0, (covered_area / effective_area) * 100) if effective_area > 0 else 0.0
        
        estimated_duration = cutting_length / self.AVG_FEED_RATE if self.AVG_FEED_RATE > 0 else 0.0
        
        return {
            'total_length': total_length,
            'coverage_percentage': coverage_percentage,
            'estimated_duration': estimated_duration
        }
    
    async def _create_trajectory_record(self, db: AsyncSession, wall: Wall, request: TrajectoryPlanRequest,
                                      path_points: List[PathPoint], metrics: Dict[str, float], start_time: float) -> Trajectory:
        """Create trajectory record in database"""
        execution_time_ms = int((time.time() - start_time) * 1000)
        algorithm = self._get_algorithm_name(request.algorithm)
        
        trajectory = Trajectory(
            wall_id=wall.id,
            name=f"{algorithm.capitalize()} - {wall.name}",
            algorithm=algorithm,
            robot_width=request.robot_width,
            overlap_percentage=request.overlap_percentage,
            resolution=request.resolution,
            total_length=metrics['total_length'],
            coverage_percentage=metrics['coverage_percentage'],
            execution_time_ms=execution_time_ms,
            estimated_duration_minutes=metrics['estimated_duration'],
            status="completed"
        )
        
        db.add(trajectory)
        await db.flush()
        
        # Create trajectory points in batches
        trajectory_points = []
        for i, point in enumerate(path_points):
            trajectory_points.append(TrajectoryPoint(
                trajectory_id=trajectory.id,
                sequence_number=i,
                x=point.x, y=point.y, z=point.z,
                orientation=point.orientation,
                tool_active=point.tool_active,
                motion_type=point.motion_type,
                feed_rate=point.feed_rate,
                planned_time=i * 0.1
            ))
            
            if len(trajectory_points) >= self.BATCH_SIZE:
                db.add_all(trajectory_points)
                await db.flush()
                trajectory_points = []
        
        if trajectory_points:
            db.add_all(trajectory_points)
        
        await db.commit()
        logger.info(f"Created trajectory {trajectory.id} with {len(path_points)} points")
        return trajectory