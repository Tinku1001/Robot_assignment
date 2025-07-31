# app/utils/geometry.py

import math
from typing import Dict, Any, Tuple, List

class GeometryUtils:
    """Utility class for geometric calculations and validations"""
    
    @staticmethod
    def validate_obstacle_geometry(
        obstacle_type: str, 
        geometry_data: Dict[str, Any], 
        wall_width: float, 
        wall_height: float
    ) -> bool:
        """Validate that obstacle geometry is valid and within wall bounds"""
        try:
            if obstacle_type == "rectangle":
                center_x = geometry_data.get("center_x", 0)
                center_y = geometry_data.get("center_y", 0)
                width = geometry_data.get("width", 0)
                height = geometry_data.get("height", 0)
                
                if width <= 0 or height <= 0:
                    return False
                
                # Check if obstacle is within wall bounds
                min_x = center_x - width / 2
                max_x = center_x + width / 2
                min_y = center_y - height / 2
                max_y = center_y + height / 2
                
                return (min_x >= 0 and max_x <= wall_width and 
                        min_y >= 0 and max_y <= wall_height)
                        
            elif obstacle_type == "circle":
                center_x = geometry_data.get("center_x", 0)
                center_y = geometry_data.get("center_y", 0)
                radius = geometry_data.get("radius", 0)
                
                if radius <= 0:
                    return False
                
                # Check if circle is within wall bounds
                return (center_x - radius >= 0 and center_x + radius <= wall_width and
                        center_y - radius >= 0 and center_y + radius <= wall_height)
            
            return False
            
        except (KeyError, TypeError, ValueError):
            return False
    
    @staticmethod
    def rectangle_bounds(center_x: float, center_y: float, width: float, height: float) -> Tuple[float, float, float, float]:
        """Calculate bounding box for a rectangle"""
        min_x = center_x - width / 2
        max_x = center_x + width / 2
        min_y = center_y - height / 2
        max_y = center_y + height / 2
        return min_x, min_y, max_x, max_y
    
    @staticmethod
    def circle_bounds(center_x: float, center_y: float, radius: float) -> Tuple[float, float, float, float]:
        """Calculate bounding box for a circle"""
        min_x = center_x - radius
        max_x = center_x + radius
        min_y = center_y - radius
        max_y = center_y + radius
        return min_x, min_y, max_x, max_y
    
    @staticmethod
    def point_in_rectangle(x: float, y: float, center_x: float, center_y: float, width: float, height: float) -> bool:
        """Check if a point is inside a rectangle"""
        return (center_x - width/2 <= x <= center_x + width/2 and
                center_y - height/2 <= y <= center_y + height/2)
    
    @staticmethod
    def point_in_circle(x: float, y: float, center_x: float, center_y: float, radius: float) -> bool:
        """Check if a point is inside a circle"""
        distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
        return distance <= radius
    
    @staticmethod
    def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> float:
        """Calculate Euclidean distance between two points"""
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    @staticmethod
    def normalize_angle(angle: float) -> float:
        """Normalize angle to [-π, π] range"""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle