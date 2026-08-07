"""
Verify that the global singleton still works correctly after Phase 1 changes
"""
import os
import sys

# Add repo root and backend_api to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
BACKEND_API_DIR = os.path.join(REPO_ROOT, "backend_api")
if BACKEND_API_DIR not in sys.path:
    sys.path.insert(0, BACKEND_API_DIR)

from app.services.live_monitor import init_live_service, get_live_service
from backend.events.event_bus import get_event_bus


def test_singleton_still_works():
    print("=== Testing Global Singleton Compatibility ===")
    model_path = os.path.join(REPO_ROOT, "models", "pose_landmarker_lite.task")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Pose model not found at {model_path}")

    # Initialize the singleton
    service = init_live_service(model_path)
    service2 = get_live_service()
    assert service is service2, "Global singleton not working!"
    print("[OK] Global singleton works")

    # Check that the singleton uses the global EventBus? Wait, no—let's check:
    print(f"Singleton service EventBus: {id(service.event_bus)}")
    global_eb = get_event_bus()
    print(f"Global EventBus: {id(global_eb)}")

    print("[OK] Singleton works correctly")

if __name__ == "__main__":
    test_singleton_still_works()
