"""
Streamlit entry point for Ergonomic Posture Analysis
"""
import sys
from pathlib import Path

# Add the repo root to Python path for imports
repo_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root))

# Import and run the frontend app
from frontend import app  # noqa: F401
