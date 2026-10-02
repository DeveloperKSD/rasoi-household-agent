"""Usage (from backend/):  python -m db.init_db   |   python -m db.init_db --reset"""
import sys
from db.seed import create_schema, reset_world

if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_world(); print("Dropped, recreated and seeded.")
    else:
        create_schema(); print("Schema ready (run with --reset to reseed).")
