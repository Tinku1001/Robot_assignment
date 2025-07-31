# tests/test_api.py
import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db, init_db

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Setup test database before running tests"""
    asyncio.run(init_db())

class TestWallsAPI:
    """Test wall CRUD operations"""
    
    def test_create_wall(self):
        """Test wall creation"""
        start_time = time.time()
        
        response = client.post("/api/v1/walls", json={
            "name": "Test Wall",
            "width": 5.0,
            "height": 3.0,
            "origin_x": 0.0,
            "origin_y": 0.0
        })
        
        response_time = time.time() - start_time
        
        assert response.status_code == 201
        assert response_time < 1.0  # Response within 1 second
        
        data = response.json()
        assert data["name"] == "Test Wall"
        assert data["width"] == 5.0
        assert data["height"] == 3.0
        
        return data["id"]  # Return wall ID for other tests
    
    def test_get_walls(self):
        """Test retrieving walls"""
        start_time = time.time()
        
        response = client.get("/api/v1/walls")
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0
        assert isinstance(response.json(), list)
    
    def test_get_wall_by_id(self):
        """Test retrieving specific wall"""
        # First create a wall
        wall_id = self.test_create_wall()
        
        start_time = time.time()
        response = client.get(f"/api/v1/walls/{wall_id}")
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0
        
        data = response.json()
        assert data["id"] == wall_id
    
    def test_wall_not_found(self):
        """Test 404 for non-existent wall"""
        response = client.get("/api/v1/walls/99999")
        assert response.status_code == 404

class TestObstaclesAPI:
    """Test obstacle CRUD operations"""
    
    def test_create_obstacle(self):
        """Test obstacle creation"""
        # First create a wall
        wall_response = client.post("/api/v1/walls", json={
            "name": "Test Wall for Obstacle",
            "width": 5.0,
            "height": 3.0
        })
        wall_id = wall_response.json()["id"]
        
        start_time = time.time()
        response = client.post(f"/api/v1/walls/{wall_id}/obstacles", json={
            "name": "Test Window",
            "obstacle_type": "rectangle",
            "geometry_data": {
                "center_x": 2.5,
                "center_y": 1.5,
                "width": 0.5,
                "height": 0.5
            }
        })
        response_time = time.time() - start_time
        
        assert response.status_code == 201
        assert response_time < 1.0
        
        data = response.json()
        assert data["name"] == "Test Window"
        assert data["obstacle_type"] == "rectangle"

class TestPlanningAPI:
    """Test trajectory planning"""
    
    def test_get_algorithms(self):
        """Test retrieving available algorithms"""
        start_time = time.time()
        response = client.get("/api/v1/planning/algorithms")
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0
        
        data = response.json()
        assert "algorithms" in data
        assert len(data["algorithms"]) >= 3  # At least 3 algorithms
    
    def test_plan_trajectory(self):
        """Test trajectory planning"""
        # Create wall first
        wall_response = client.post("/api/v1/walls", json={
            "name": "Planning Test Wall",
            "width": 3.0,
            "height": 3.0
        })
        wall_id = wall_response.json()["id"]
        
        start_time = time.time()
        response = client.post("/api/v1/planning/plan", json={
            "wall_id": wall_id,
            "algorithm": "boustrophedon",
            "robot_width": 0.1,
            "overlap_percentage": 20.0,
            "resolution": 0.05
        })
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 5.0  # Planning should complete within 5 seconds
        
        data = response.json()
        assert "trajectory_id" in data
        assert "total_points" in data
        assert "total_length" in data
        assert data["total_points"] > 0

class TestPerformance:
    """Test API performance requirements"""
    
    def test_concurrent_requests(self):
        """Test handling multiple concurrent requests"""
        import threading
        import time
        
        def make_request():
            response = client.get("/api/v1/walls")
            return response.status_code == 200
        
        # Create 10 concurrent requests
        threads = []
        results = []
        
        start_time = time.time()
        for _ in range(10):
            thread = threading.Thread(target=lambda: results.append(make_request()))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        assert all(results)  # All requests successful
        assert total_time < 3.0  # All requests completed within 3 seconds
