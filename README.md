# Wall Finishing Robot Control System

Advanced control system for wall-finishing robots with intelligent path planning and obstacle avoidance.

## Features

- Path planning with 3 algorithms (Boustrophedon, Spiral, Zigzag)
- Obstacle detection and avoidance
- SQLite database with optimized indexing
- FastAPI backend with async operations
- Web-based 2D visualization
- Comprehensive API testing

## Installation

```bash
git clone <repository-url>
cd wall-finishing-robot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
