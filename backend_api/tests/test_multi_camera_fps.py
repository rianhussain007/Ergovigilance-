"""
Phase 1 test: Run two cameras (or one real + one mock) and track FPS
"""
import os
import sys
import time
import threading
import numpy as np
import cv2

# Add repo root and backend_api to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
BACKEND_API_DIR = os.path.join(REPO_ROOT, "backend_api")
if BACKEND_API_DIR not in sys.path:
    sys.path.insert(0, BACKEND_API_DIR)

from app.services.live_monitor import LiveMonitoringService
from backend.events.event_bus import EventBus


class MockVideoCapture:
    """Synthetic video source that generates dummy frames"""
    def __init__(self, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.running = True

    def isOpened(self):
        return self.running

    def read(self):
        if not self.running:
            return False, None
        # Generate a dummy frame (solid color)
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        return True, frame

    def set(self, prop, value):
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        if prop == cv2.CAP_PROP_FPS:
            return self.fps
        return 0

    def release(self):
        self.running = False


def test_multi_camera_fps():
    model_path = os.path.join(REPO_ROOT, "models", "pose_landmarker_lite.task")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Pose model not found at {model_path}")

    print("=== Starting FPS Test ===")

    # Find available cameras
    print("Checking available cameras...")
    available_cameras = []
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
            cap.release()
    print(f"Available physical cameras: {available_cameras}")

    # Create services with isolated EventBuses
    service1 = LiveMonitoringService(model_path, event_bus=EventBus())
    service2 = LiveMonitoringService(model_path, event_bus=EventBus())

    # Track FPS for each service
    fps_stats1 = []
    fps_stats2 = []
    stop_event = threading.Event()

    def track_fps(service, stats_list):
        while not stop_event.is_set() and service.is_running():
            state = service.get_state_snapshot()
            if state.fps > 0:
                stats_list.append(state.fps)
            time.sleep(0.5)

    # Determine sources
    use_mock = len(available_cameras) < 2
    cam1_idx = available_cameras[0] if available_cameras else 0

    print(f"\nStarting sessions... {'1 real + 1 mock' if use_mock else '2 real cameras'}")

    # Start service 1
    session1 = service1.start_session(camera_index=cam1_idx, worker_id="worker-1")

    # Start service 2 (mock if needed)
    if use_mock:
        # Monkey-patch service2 to use mock camera
        service2.cap = MockVideoCapture()
        # Manually start the processing thread
        service2.engine.initialize()
        service2.analytics.reset()
        from datetime import datetime
        service2.state.session_active = True
        service2.state.session_id = f"SESS-MOCK-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        service2.state.camera_status = "active"
        service2._running = True
        service2._fps_start = time.perf_counter()
        service2._last_frame_time = time.perf_counter()
        service2.thread = threading.Thread(target=service2._process_loop, daemon=True)
        service2.thread.start()
        session2 = service2.state.session_id
    else:
        session2 = service2.start_session(camera_index=available_cameras[1], worker_id="worker-2")

    print(f"Session 1: {session1}")
    print(f"Session 2: {session2}")

    # Start FPS tracking threads
    tracker1 = threading.Thread(target=track_fps, args=(service1, fps_stats1), daemon=True)
    tracker2 = threading.Thread(target=track_fps, args=(service2, fps_stats2), daemon=True)
    tracker1.start()
    tracker2.start()

    # Run for 30 seconds
    test_duration = 30
    print(f"\nRunning test for {test_duration} seconds...")
    for i in range(test_duration):
        time.sleep(1)
        print(f"Elapsed: {i+1}/{test_duration}s")

    # Stop everything
    print("\nStopping sessions...")
    stop_event.set()
    service1.stop_session()
    service2.stop_session()
    tracker1.join()
    tracker2.join()

    # Print results
    print("\n=== Results ===")
    if fps_stats1:
        avg1 = sum(fps_stats1) / len(fps_stats1)
        max1 = max(fps_stats1)
        min1 = min(fps_stats1)
        print(f"Service 1 (camera {cam1_idx}):")
        print(f"  Avg FPS: {avg1:.1f}")
        print(f"  Max FPS: {max1:.1f}")
        print(f"  Min FPS: {min1:.1f}")
    if fps_stats2:
        avg2 = sum(fps_stats2) / len(fps_stats2)
        max2 = max(fps_stats2)
        min2 = min(fps_stats2)
        print(f"\nService 2 ({'mock' if use_mock else f'camera {available_cameras[1]}'}):")
        print(f"  Avg FPS: {avg2:.1f}")
        print(f"  Max FPS: {max2:.1f}")
        print(f"  Min FPS: {min2:.1f}")

    print("\n=== FPS Test Complete ===")


if __name__ == "__main__":
    test_multi_camera_fps()
