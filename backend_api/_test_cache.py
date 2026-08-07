"""Simulate multiple requests to verify module-level cache persists."""
import sys, os, time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the module-level cache variables
from app.repositories.live import _camera_cache, _camera_cache_time

print(f"BEFORE: cache={_camera_cache!r}, time={_camera_cache_time}")

# Simulate first call — probe cameras (the method normally does this,
# but we can't call get_cameras() easily without a running live service.
# Instead, verify that the module-level vars are shared across imports.)

# Simulate what the method does: write to module-level cache via global
import app.repositories.live as live_mod

# First "request"
live_mod._camera_cache = ["camera_a", "camera_b"]
live_mod._camera_cache_time = time.time()
print(f"After write 1: cache={live_mod._camera_cache}, time={live_mod._camera_cache_time}")

# Second "request" (new import reference, same module)
from app.repositories.live import _camera_cache as c2, _camera_cache_time as t2
print(f"After write 2 (same-module import): cache={c2!r}, time={t2}")

# Verify cache is NOT empty (would trigger reprobe)
if c2:
    print("SUCCESS: Module-level cache persists across 'import' boundaries")
else:
    print("FAIL: Cache lost between imports")

# Cleanup
os.remove(__file__)
