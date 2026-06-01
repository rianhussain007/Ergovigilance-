import sys
from pathlib import Path

# Add the repo root to Python path for imports
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Import the Streamlit app
if __name__ == "__main__":
    from frontend.app import *  # noqa: F401, F403
