# Performance & Alert Management Optimizations

## Overview
This document details the performance optimizations and alert management improvements implemented to address:
1. Camera lag/slowness during live monitoring
2. Poor alert display and management
3. Need for attractive, professional UI for pilot customers

## Performance Optimizations

### 1. CV Pipeline Performance (`backend/services/performance.py`)

#### FrameSkipper
- **Purpose**: Maintains target FPS (15 FPS default) while allowing burst processing
- **How it works**: Skips frames when processing is too slow, with a max skip limit
- **Benefit**: Consistent frame rate even under CPU load

#### FeatureCache
- **Purpose**: Caches computed features to avoid redundant calculations
- **How it works**: Stores feature results keyed by keypoint hash, with TTL
- **Benefit**: Faster processing when same pose is processed multiple times

#### ComputationalShortcuts
- **Purpose**: Reduces unnecessary calculations when pose hasn't changed
- **How it works**: Tracks keypoint movement and feature changes
- **Benefit**: Skips full computation when minimal movement detected

#### PerformanceMonitor
- **Purpose**: Tracks timing metrics for debugging and optimization
- **How it works**: Records inference, feature, and context evaluation times
- **Benefit**: Visibility into pipeline performance

### 2. Pose Engine Optimizations (`backend/services/pose_engine.py`)

#### Frame Skipping Integration
```python
# Skip frames if we're ahead of schedule
if not frame_skipper.should_process():
    return ProcessedFrame(...)  # Lightweight result
```

#### Feature Caching Integration
```python
# Check cache first to avoid redundant feature extraction
cached_features = feature_cache.get(keypoints)
if cached_features is not None:
    features = cached_features.get('features', {})
    # ... use cached features
else:
    features, unavailable, approximate = extract_features_from_keypoints(keypoints)
    feature_cache.set(keypoints, {...})  # Cache for next time
```

#### Performance Monitoring Integration
```python
# Record timing for each frame
start_time = time.perf_counter()
# ... process frame
inference_time = time.perf_counter() - inference_start
performance_monitor.record_frame_time(...)
```

## Alert Management Improvements

### 1. New AlertCenter Component (`ui_posture/src/components/common/AlertCenter.tsx`)

#### Features:
- **Modern UI**: Card-based design with severity-based color coding
- **Alert Statistics**: 24-hour summary (total, critical, high, resolved)
- **Expandable Alerts**: Click to see details (confidence, trigger rule, severity)
- **Role-Based Actions**: 
  - Acknowledge: Supervisor, Safety Mgr, Admin
  - Resolve: Safety Mgr, Admin only
- **Search & Filters**: Filter by category (Critical, Warning, Info, Resolved)
- **Time-Ago Display**: "Just now", "5m ago", "2h ago"

#### Visual Design:
- Gradient backgrounds based on severity
- Severity-based border colors
- Pulse animation for critical/high alerts
- Expandable cards with detailed information

### 2. Improved Alert Toasts (`ui_posture/src/components/common/AlertToast.tsx`)

#### Features:
- **Better Visual Design**: Gradient backgrounds with severity colors
- **Progress Bar**: Shows remaining time before auto-dismiss
- **Faster Response**: Reduced sustained threshold from 15s to 10s
- **Severity Escalation**: Re-toasts when alert severity changes

### 3. Updated Alert Toast Hook (`ui_posture/src/hooks/useAlertToasts.ts`)

#### Improvements:
- **Severity Sorting**: Critical alerts shown first
- **Escalation Handling**: Re-toasts on severity change
- **Better Timing**: 10s sustained threshold, 8s display duration

## Testing Results

### Backend Tests
- **Total**: 222 tests passed, 1 skipped
- **Performance**: All performance optimizations compile and run correctly
- **Alert Engine**: All alert-related tests pass

### Standalone Engine Tests
- **Total**: 15/15 tests passed
- **Context Engine**: All context intelligence tests pass

### Frontend Build
- **Status**: ✅ Builds successfully
- **Bundle Size**: 1,200 KB JS, 93 KB CSS (gzipped: 329 KB JS, 15 KB CSS)
- **Warnings**: Dynamic import warning (non-critical)

## What You Should See

### Live Monitoring
- **Smoother Camera Feed**: Consistent FPS with frame skipping
- **Reduced Lag**: Feature caching reduces redundant calculations
- **Performance Metrics**: Available in backend logs

### Alert Center (Bell Icon)
- **Professional UI**: Modern, card-based design
- **Quick Overview**: 24-hour statistics at top
- **Easy Filtering**: Search and category filters
- **Action Buttons**: Role-based acknowledge/resolve

### Alert Toasts
- **Attractive Design**: Gradient backgrounds with severity colors
- **Progress Bar**: Shows time remaining
- **Faster Response**: Alerts appear more quickly

## MVP Value

The new Alert Center adds significant value:
1. **Professional Appearance**: Looks like a real product, not a prototype
2. **Actionable Insights**: Confidence scores, trigger rules, timestamps
3. **Role-Based Access**: Proper permissions for actions
4. **Statistics Dashboard**: Quick overview of alert activity

## Next Steps

### Immediate Testing
1. Start a monitoring session and verify camera smoothness
2. Check the Alert Center UI (bell icon)
3. Verify alert toasts appear correctly

### Follow-up Enhancements
1. **Alert Grouping**: Group related alerts (e.g., same trigger rule)
2. **Alert Analytics**: Detailed statistics and trends
3. **Custom Alert Rules**: Allow safety managers to configure thresholds
4. **Mobile Optimization**: Responsive design for tablets/phones

## Configuration

### Performance Tuning
```bash
# Adjust target FPS (default: 15)
export POSE_PROCESS_FPS=15

# Adjust frame skip limit (default: 3)
export ERGOVIGILANCE_MAX_SKIP=3

# Adjust feature cache TTL (default: 0.5s)
export ERGOVIGILANCE_CACHE_TTL=0.5
```

### Alert Tuning
```bash
# Adjust sustained alert threshold (default: 10s)
export ERGOVIGILANCE_ALERT_SUSTAINED_MS=10000

# Adjust toast display duration (default: 8s)
export ERGOVIGILANCE_TOAST_DURATION_MS=8000
```
