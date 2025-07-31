from sqlalchemy import Column, Integer, Float, String, DateTime, Text, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship, declarative_mixin
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

# Mixins for common functionality
@declarative_mixin
class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

@declarative_mixin
class UUIDMixin:
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

class BaseModel(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)

class Wall(BaseModel, TimestampMixin, UUIDMixin):
    __tablename__ = "walls"
    
    name = Column(String(100), index=True, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    origin_x = Column(Float, default=0.0)
    origin_y = Column(Float, default=0.0)
    
    obstacles = relationship("Obstacle", back_populates="wall", cascade="all, delete-orphan")
    trajectories = relationship("Trajectory", back_populates="wall", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_wall_dimensions', 'width', 'height'),
        Index('idx_wall_created', 'created_at'),
    )

class Obstacle(BaseModel):
    __tablename__ = "obstacles"
    
    wall_id = Column(Integer, ForeignKey("walls.id"), nullable=False)
    name = Column(String(100), nullable=False)
    obstacle_type = Column(String(50), default="rectangle")
    min_x = Column(Float, nullable=False)
    min_y = Column(Float, nullable=False)
    max_x = Column(Float, nullable=False)
    max_y = Column(Float, nullable=False)
    geometry_data = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    wall = relationship("Wall", back_populates="obstacles")
    
    __table_args__ = (
        Index('idx_obstacle_spatial', 'min_x', 'min_y', 'max_x', 'max_y'),
        Index('idx_obstacle_wall', 'wall_id'),
        Index('idx_obstacle_type', 'obstacle_type'),
    )

class Trajectory(BaseModel, TimestampMixin, UUIDMixin):
    __tablename__ = "trajectories"
    
    wall_id = Column(Integer, ForeignKey("walls.id"), nullable=False)
    name = Column(String(100))
    algorithm = Column(String(50), nullable=False)
    status = Column(String(20), default="completed")
    robot_width = Column(Float, nullable=False)
    overlap_percentage = Column(Float, nullable=False)
    resolution = Column(Float, nullable=False)
    total_points = Column(Integer, default=0)
    total_length = Column(Float, default=0.0)
    coverage_percentage = Column(Float, default=0.0)
    execution_time_ms = Column(Integer, default=0)
    estimated_duration_minutes = Column(Float, default=0.0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    wall = relationship("Wall", back_populates="trajectories")
    points = relationship("TrajectoryPoint", back_populates="trajectory", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_trajectory_status', 'status', 'created_at'),
        Index('idx_trajectory_wall', 'wall_id'),
        Index('idx_trajectory_algorithm', 'algorithm'),
    )

class TrajectoryPoint(BaseModel):
    __tablename__ = "trajectory_points"
    
    trajectory_id = Column(Integer, ForeignKey("trajectories.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, default=0.0)
    orientation = Column(Float, default=0.0)
    tool_active = Column(Boolean, default=True)
    feed_rate = Column(Float, default=100.0)
    motion_type = Column(String(20), default="linear")
    planned_time = Column(Float)
    actual_time = Column(Float)
    
    trajectory = relationship("Trajectory", back_populates="points")
    
    __table_args__ = (
        Index('idx_trajectory_point_spatial', 'x', 'y'),
        Index('idx_trajectory_point_sequence', 'trajectory_id', 'sequence_number'),
        Index('idx_trajectory_point_time', 'planned_time'),
    )

class SystemLog(BaseModel):
    __tablename__ = "system_logs"
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    level = Column(String(10), nullable=False)
    component = Column(String(50))
    message = Column(Text, nullable=False)
    request_id = Column(String(36))
    user_id = Column(String(36))
    endpoint = Column(String(100))
    execution_time_ms = Column(Integer)
    memory_usage_mb = Column(Float)
    context_data = Column(Text)
    
    __table_args__ = (
        Index('idx_log_timestamp', 'timestamp'),
        Index('idx_log_level', 'level'),
        Index('idx_log_component', 'component'),
        Index('idx_log_request', 'request_id'),
    )