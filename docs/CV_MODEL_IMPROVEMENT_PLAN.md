# CV Model Improvement Plan: Task Recognition & Context Awareness

## Executive Summary

The current task recognition and context awareness systems are **functionally complete but trained on synthetic data only**. This plan addresses the critical gap: moving from synthetic training to real factory footage, improving model accuracy, and building a proper data collection pipeline.

**Current State:**
- Task classifier: HistGradientBoosting on 19 features, 7 classes, trained on synthetic poses
- Context engine: Rule-based (deterministic), no ML scoring
- Accuracy: 76.9% (circular — model vs its own thresholds)
- Ground truth: Zero human-labeled frames exist

**Target State:**
- Task classifier: >90% accuracy on real factory footage
- Context engine: ML-augmented scoring with learned patterns
- Data: 500+ labeled frames from real factory sessions
- Validation: Human-ergonomist-validated risk scores

---

## Phase 1: Data Collection Pipeline (Week 1-2)

### 1.1 Real Factory Footage Collection

**Objective:** Capture 10-20 minutes of real factory footage per task class.

**Required Equipment:**
- USB webcam (720p minimum, 30fps)
- Laptop with GPU (for pose estimation)
- Clipboard for manual task labeling

**Collection Protocol:**
1. Position camera at workstation (front-facing, full body visible)
2. Record 2-3 workers per shift performing each task
3. Manually log task transitions with timestamps
4. Capture diverse conditions: lighting, PPE, body types

**Target Footage:**
| Task Class | Minimum Duration | Target Duration |
|------------|------------------|-----------------|
| Neutral Standing | 2 min | 5 min |
| Assembly Work | 5 min | 10 min |
| Reaching | 3 min | 5 min |
| Lifting / Picking | 3 min | 5 min |
| Inspection | 2 min | 5 min |
| Seated Work | 3 min | 5 min |
| Walking / Moving | 2 min | 5 min |

### 1.2 Ground Truth Labeling

**Objective:** Create human-labeled dataset with ergonomic risk annotations.

**Labeling Protocol:**
1. Extract frames at 1fps from collected footage
2. Present frames to trained ergonomist (or use REBA/RULA scoring)
3. Label each frame with:
   - Task class (7 classes)
   - Risk level (LOW/MEDIUM/HIGH)
   - RULA/REBA score (if available)
   - Key joint angles (optional, for validation)

**Tools:**
- `scripts/label_frames.py` — already exists for CLI labeling
- `scripts/evaluate_ground_truth.py` — already exists for evaluation

### 1.3 Dataset Structure

**Target Format:** CSV with columns:
```
frame_id, timestamp, task_label, risk_level, rula_score, reba_score,
neck_flexion, trunk_flexion, left_shoulder_elev, right_shoulder_elev,
shoulder_symmetry, alignment_deviation, knee_angle, elbow_flexion_angle,
upper_arm_angle_from_vertical, forward_head_posture, head_tilt_angle,
wrist_deviation_angle, stance_stability, weight_shift_offset,
hand_reach_ratio, finger_spread_ratio, stance_width_ratio,
movement_velocity, wrist_movement_velocity, keypoints_33d
```

---

## Phase 2: Model Retraining (Week 2-3)

### 2.1 Task Classifier v3

**Objective:** Retrain task classifier on real factory footage.

**Approach:**
1. Use `scripts/build_task_dataset.py` to extract features from real clips
2. Train new model with `scripts/train_task_model_v2.py --data data/processed/task_clips_features.csv`
3. Validate against held-out real footage (not synthetic)

**Improvements over v2:**
- Real-world pose variation (lighting, PPE, body types)
- Temporal context (sequence of frames, not isolated poses)
- Uncertainty estimation (confidence calibration)

**Model Architecture Options:**
1. **HistGradientBoosting (current)** — fast, interpretable, good baseline
2. **Random Forest** — ensemble diversity, robust to noise
3. **LightGBM/XGBoost** — gradient boosting with regularization
4. **Temporal CNN** — captures frame sequences (future enhancement)

### 2.2 Context Engine Augmentation

**Objective:** Add ML-based scoring to the rule-based context engine.

**Current Limitations:**
- Rules are static thresholds (no learning from data)
- No temporal pattern recognition (each frame independent)
- No anomaly detection (unusual postures not flagged)

**Proposed Enhancement:**
1. **Feature importance learning** — which features matter most for risk?
2. **Temporal patterns** — sequences of postures that indicate risk
3. **Anomaly detection** — unusual postures that don't fit normal patterns
4. **Confidence calibration** — how sure is the system about each assessment?

**Implementation:**
```python
# Example: ML-augmented risk scoring
class MLContextScorer:
    def __init__(self, rule_engine, ml_model):
        self.rule_engine = rule_engine
        self.ml_model = ml_model  # trained on real data
    
    def score(self, features, temporal_context):
        # Rule-based score (authoritative)
        rule_score = self.rule_engine.score(features)
        
        # ML-based score (advisory)
        ml_score = self.ml_model.predict(features, temporal_context)
        
        # Combine: rules anchor, ML provides confidence/context
        return self.combine(rule_score, ml_score)
```

---

## Phase 3: Validation & Testing (Week 3-4)

### 3.1 Accuracy Validation

**Metrics:**
- **Task classification accuracy** — % of frames correctly classified
- **Risk level agreement** — % agreement with human ergonomist
- **Temporal consistency** — smooth transitions between tasks
- **Confidence calibration** — predicted confidence matches actual accuracy

**Test Protocol:**
1. Run model on held-out real footage
2. Compare predictions to human labels
3. Generate confusion matrix per task class
4. Identify failure modes (which tasks are confused?)

### 3.2 Edge Case Testing

**Scenarios:**
- Worker partially out of frame
- Poor lighting conditions
- Heavy PPE (vests, helmets)
- Multiple workers in frame
- Rapid task transitions
- Unusual postures (stretching, bending)

### 3.3 Performance Benchmarks

**Latency:**
- Feature extraction: <5ms per frame
- Task classification: <1ms per frame
- Context scoring: <2ms per frame
- Total pipeline: <10ms per frame (100fps capable)

**Memory:**
- Model size: <10MB
- Feature buffer: <1MB (temporal window)
- Total footprint: <50MB

---

## Phase 4: Deployment & Monitoring (Week 4+)

### 4.1 A/B Testing

**Strategy:**
1. Run v2 (synthetic) and v3 (real) models in parallel
2. Compare predictions on live footage
3. Gradually shift traffic to v3 when confidence is high
4. Monitor drift and accuracy degradation

### 4.2 Continuous Learning

**Pipeline:**
1. Collect misclassified frames (low confidence predictions)
2. Human review of ambiguous cases
3. Retrain model monthly with new data
4. Deploy updated model with version tracking

### 4.3 Monitoring Dashboard

**Metrics to Track:**
- Task classification distribution over time
- Risk level distribution per worker/station
- Model confidence trends
- Anomaly detection alerts
- Data quality metrics (missing landmarks, occlusion)

---

## Implementation Checklist

### Immediate Actions (This Week)
- [ ] Set up data collection workstation (camera + laptop)
- [ ] Capture 5 minutes of each task class from real factory
- [ ] Label 100 frames manually (ground truth baseline)
- [ ] Run `build_task_dataset.py` on real footage
- [ ] Train v3 model and compare to v2

### Short-term (Next 2 Weeks)
- [ ] Capture 10+ minutes per task class
- [ ] Label 500+ frames with ergonomist validation
- [ ] Train v3 model on real data
- [ ] Validate against held-out test set
- [ ] Deploy v3 to production with monitoring

### Medium-term (Month 2)
- [ ] Collect 1000+ labeled frames
- [ ] Add temporal context to model (sequence features)
- [ ] Implement ML-augmented context scoring
- [ ] Build continuous learning pipeline
- [ ] Publish validation results

---

## Resources Needed

### Hardware
- USB webcam (720p, 30fps) — $50-100
- Laptop with GPU (GTX 1060+ or equivalent) — existing or $500
- External hard drive for footage — $50

### Software
- MediaPipe (already installed)
- scikit-learn (already installed)
- OpenCV (already installed)
- Label Studio (optional, for web-based labeling)

### Human Resources
- Factory access (1-2 hours per week for footage collection)
- Trained ergonomist (2-4 hours for validation labeling)
- Developer time (20-30 hours for implementation)

### Data
- 10-20 minutes of real factory footage per task class
- 500+ human-labeled frames
- Ergonomist validation of risk scores

---

## Success Criteria

### Minimum Viable Improvement
- [ ] Task classification accuracy >85% on real footage (vs 76.9% synthetic)
- [ ] Risk level agreement >80% with human ergonomist
- [ ] Latency <10ms per frame
- [ ] Zero crashes on edge cases

### Target Performance
- [ ] Task classification accuracy >90%
- [ ] Risk level agreement >90%
- [ ] Temporal consistency score >0.8
- [ ] Confidence calibration error <5%

### Stretch Goals
- [ ] Multi-person tracking (Tier 3 roadmap item)
- [ ] Object-aware context (tool/load detection)
- [ ] Predictive risk forecasting (early warning)

---

## Risk Mitigation

### Risk 1: Insufficient Real Footage
**Mitigation:** Augment with synthetic data (current approach) + domain adaptation techniques

### Risk 2: Labeling Inconsistency
**Mitigation:** Clear labeling guidelines, inter-rater reliability checks, consensus labeling

### Risk 3: Model Overfitting to Factory Conditions
**Mitigation:** Cross-validation across workers/stations, regularization, diverse training data

### Risk 4: Deployment Latency
**Mitigation:** Model quantization, feature caching, async inference

---

## References

1. Fan et al. (2024). 3D pose estimation dataset for ergonomic risk assessment in construction. *Automation in Construction*, 164, 105452.
2. Ciccarelli et al. (2025). Empowering industry 5.0: automated sensor-based ergonomic risk assessment. *IJIDeM*, 19, 7731–7753.
3. Cruciata et al. (2025). Lightweight Vision Transformer for frame-level ergonomic posture classification. *Sensors*, 25(15), 4750.
4. De Coninck et al. (2025). Enabling privacy-aware AI-based ergonomic analysis. *Procedia CIRP*.

---

*Plan created: August 27, 2026*
*Status: Ready for execution*
*Owner: ErgoVigilance CV Team*
