# app/models/pydantic_models.py

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Enums
class ObstacleType(str, Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"

class TrajectoryStatus(str, Enum):
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"

class MotionType(str, Enum):
    LINEAR = "linear"
    ARC = "arc"
    RAPID = "rapid"

class Algorithm(str, Enum):
    BOUSTROPHEDON = "boustrophedon"
    SPIRAL = "spiral"
    ZIGZAG = "zigzag"

# Base Classes
class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class TimestampedResponse(BaseResponse):
    created_at: datetime
    updated_at: Optional[datetime] = None

# Request Models
class WallCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    width: float = Field(..., gt=0, le=100)
    height: float = Field(..., gt=0, le=100)
    origin_x: float = Field(default=0.0, ge=-1000, le=1000)
    origin_y: float = Field(default=0.0, ge=-1000, le=1000)

class WallUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    width: Optional[float] = Field(None, gt=0, le=100)
    height: Optional[float] = Field(None, gt=0, le=100)
    origin_x: Optional[float] = Field(None, ge=-1000, le=1000)
    origin_y: Optional[float] = Field(None, ge=-1000, le=1000)

class ObstacleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    obstacle_type: ObstacleType = ObstacleType.RECTANGLE
    geometry_data: Dict[str, Any]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Window",
                "obstacle_type": "rectangle",
                "geometry_data": {"width": 0.25, "height": 0.25, "center_x": 2.5, "center_y": 2.5}
            }
        }
    )

class TrajectoryPlanRequest(BaseModel):
    wall_id: int
    algorithm: Algorithm = Algorithm.BOUSTROPHEDON
    robot_width: float = Field(default=0.1, gt=0, le=1)
    overlap_percentage: float = Field(default=20, ge=0, le=50)
    resolution: float = Field(default=0.01, gt=0, le=0.1)

# Response Models
class ObstacleResponse(BaseResponse):
    id: int
    wall_id: int
    name: str
    obstacle_type: str
    geometry_data: Dict[str, Any]
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    created_at: datetime

class WallResponse(TimestampedResponse):
    id: int
    uuid: str
    name: str
    width: float
    height: float
    origin_x: float
    origin_y: float
    obstacles: List[ObstacleResponse] = []

class TrajectoryPointResponse(BaseResponse):
    sequence_number: int
    x: float
    y: float
    z: float
    orientation: float
    tool_active: bool
    motion_type: str
    planned_time: Optional[float]
    feed_rate: float

class TrajectoryResponse(TimestampedResponse):
    id: int
    uuid: str
    wall_id: int
    name: Optional[str]
    algorithm: str
    status: str
    robot_width: float
    overlap_percentage: float
    resolution: float
    total_points: int
    total_length: float
    coverage_percentage: float
    execution_time_ms: int
    estimated_duration_minutes: float
    points: List[TrajectoryPointResponse] = []

class PlanningResult(BaseModel):
    trajectory_id: int
    wall_id: int
    algorithm: str
    total_points: int
    total_length: float
    coverage_percentage: float
    execution_time_ms: int
    estimated_duration_minutes: float
    status: str

class SystemStatusResponse(BaseModel):
    status: str
    timestamp: float
    system: Dict[str, Any]
    process: Dict[str, Any]

class AlgorithmInfo(BaseModel):
    name: str
    display_name: str
    description: str
    best_for: str

class AlgorithmsResponse(BaseModel):
    algorithms: List[AlgorithmInfo]

class ErrorResponse(BaseModel):
    error: str
    status_code: int
    request_id: Optional[str] = None
    timestamp: float

class SuccessResponse(BaseModel):
    message: str
    status_code: int = 200
    timestamp: float