"""Performance optimization utilities for the CV pipeline.

Provides frame skipping, feature caching, and computational shortcuts
to reduce latency during live monitoring.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Optional


class FrameSkipper:
    """Adaptive frame skipper that maintains target FPS.
    
    Skips frames when processing is too slow, allowing the pipeline
    to maintain a consistent frame rate even under load.
    """
    
    def __init__(self, target_fps: float = 15.0, max_skip: int = 3):
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.max_skip = max_skip
        self._last_process_time: float = 0.0
        self._frame_count: int = 0
        self._skip_count: int = 0
        
    def should_process(self) -> bool:
        """Determine if current frame should be processed."""
        now = time.perf_counter()
        elapsed = now - self._last_process_time
        
        # Always process if enough time has passed
        if elapsed >= self.frame_interval:
            self._last_process_time = now
            self._frame_count += 1
            self._skip_count = 0
            return True
        
        # Skip if we're ahead of schedule
        if self._skip_count < self.max_skip:
            self._skip_count += 1
            return False
        
        # Process anyway if we've skipped too many
        self._last_process_time = now
        self._frame_count += 1
        self._skip_count = 0
        return True
    
    @property
    def effective_fps(self) -> float:
        """Calculate effective FPS based on frame processing times."""
        if self._frame_count == 0:
            return 0.0
        return self._frame_count / (time.perf_counter() - self._last_process_time + self.frame_interval * self._frame_count)


class FeatureCache:
    """Cache computed features to avoid redundant calculations.
    
    Stores feature results keyed by a hash of the input keypoints,
    allowing reuse when the same pose is processed multiple times.
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: float = 0.5):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: deque[tuple[str, float, dict]] = deque(maxlen=max_size)
        
    def _hash_keypoints(self, keypoints: list[list[float]]) -> str:
        """Create a hash key from keypoints for cache lookup."""
        if not keypoints:
            return ""
        # Use a subset of keypoints for faster hashing
        # Focus on key joints: shoulders, hips, knees, elbows
        key_indices = [11, 12, 23, 24, 25, 26, 13, 14]  # MediaPipe indices
        key_points = []
        for idx in key_indices:
            if idx < len(keypoints):
                # Round to reduce precision for better cache hits
                kp = keypoints[idx]
                key_points.append(f"{kp[0]:.1f},{kp[1]:.1f}")
        return "|".join(key_points)
    
    def get(self, keypoints: list[list[float]]) -> Optional[dict]:
        """Retrieve cached features if available and fresh."""
        key = self._hash_keypoints(keypoints)
        if not key:
            return None
        
        now = time.time()
        for cached_key, timestamp, features in self._cache:
            if cached_key == key and (now - timestamp) < self.ttl_seconds:
                return features
        return None
    
    def set(self, keypoints: list[list[float]], features: dict) -> None:
        """Store computed features in cache."""
        key = self._hash_keypoints(keypoints)
        if key:
            self._cache.append((key, time.time(), features))
    
    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()


class ComputationalShortcuts:
    """Provide computational shortcuts for common scenarios.
    
    Reduces unnecessary calculations when the pose hasn't changed
    significantly or when certain features are known to be stable.
    """
    
    def __init__(self):
        self._prev_risk_level: str = "LOW"
        self._stable_frame_count: int = 0
        self._stability_threshold: int = 5
        
    def should_compute_full_features(self, keypoints: list[list[float]], 
                                      prev_keypoints: Optional[list[list[float]]]) -> bool:
        """Determine if full feature computation is needed.
        
        Returns False if the pose hasn't changed significantly and
        we can reuse previous features with minor adjustments.
        """
        if prev_keypoints is None or not keypoints:
            return True
        
        # Calculate keypoint movement
        key_indices = [11, 12, 23, 24]  # Shoulders and hips
        total_movement = 0.0
        
        for idx in key_indices:
            if idx < len(keypoints) and idx < len(prev_keypoints):
                dx = keypoints[idx][0] - prev_keypoints[idx][0]
                dy = keypoints[idx][1] - prev_keypoints[idx][1]
                total_movement += (dx * dx + dy * dy) ** 0.5
        
        # If movement is minimal, we might skip full computation
        return total_movement > 10.0  # Threshold in pixels
    
    def should_compute_risk(self, features: dict, prev_features: Optional[dict]) -> bool:
        """Determine if risk computation is needed.
        
        Returns False if features haven't changed enough to affect risk.
        """
        if prev_features is None:
            return True
        
        # Check key risk features
        risk_features = ['neck_flexion', 'trunk_flexion', 'shoulder_elev']
        for feature in risk_features:
            curr = features.get(feature, 0.0)
            prev = prev_features.get(feature, 0.0)
            if abs(curr - prev) > 2.0:  # 2 degree threshold
                return True
        
        return False
    
    def update_stability(self, risk_level: str) -> None:
        """Track risk level stability for adaptive computation."""
        if risk_level == self._prev_risk_level:
            self._stable_frame_count += 1
        else:
            self._stable_frame_count = 0
            self._prev_risk_level = risk_level
    
    @property
    def is_stable(self) -> bool:
        """Check if the risk level has been stable."""
        return self._stable_frame_count >= self._stability_threshold


class PerformanceMonitor:
    """Monitor and report pipeline performance metrics."""
    
    def __init__(self):
        self._frame_times: deque[float] = deque(maxlen=100)
        self._inference_times: deque[float] = deque(maxlen=100)
        self._feature_times: deque[float] = deque(maxlen=100)
        self._context_times: deque[float] = deque(maxlen=100)
        
    def record_frame_time(self, total_time: float, inference_time: float, 
                         feature_time: float, context_time: float) -> None:
        """Record timing for one frame."""
        self._frame_times.append(total_time)
        self._inference_times.append(inference_time)
        self._feature_times.append(feature_time)
        self._context_times.append(context_time)
    
    @property
    def avg_fps(self) -> float:
        """Calculate average FPS."""
        if not self._frame_times:
            return 0.0
        avg_time = sum(self._frame_times) / len(self._frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0.0
    
    @property
    def avg_inference_ms(self) -> float:
        """Calculate average inference time in milliseconds."""
        if not self._inference_times:
            return 0.0
        return (sum(self._inference_times) / len(self._inference_times)) * 1000
    
    @property
    def avg_feature_ms(self) -> float:
        """Calculate average feature extraction time in milliseconds."""
        if not self._feature_times:
            return 0.0
        return (sum(self._feature_times) / len(self._feature_times)) * 1000
    
    @property
    def avg_context_ms(self) -> float:
        """Calculate average context evaluation time in milliseconds."""
        if not self._context_times:
            return 0.0
        return (sum(self._context_times) / len(self._context_times)) * 1000
    
    def get_metrics(self) -> dict:
        """Get all performance metrics."""
        return {
            "fps": round(self.avg_fps, 1),
            "inference_ms": round(self.avg_inference_ms, 1),
            "feature_ms": round(self.avg_feature_ms, 1),
            "context_ms": round(self.avg_context_ms, 1),
            "total_ms": round(self.avg_inference_ms + self.avg_feature_ms + self.avg_context_ms, 1),
        }


# Global instances
frame_skipper = FrameSkipper()
feature_cache = FeatureCache()
computational_shortcuts = ComputationalShortcuts()
performance_monitor = PerformanceMonitor()
