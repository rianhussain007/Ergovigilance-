# ErgoVigilance Project Explanation

**Purpose of this document:**  
This file explains the ErgoVigilance project in simple but detailed language so a professor, mentor, or guide can quickly understand what we are building, what already works, what technical approach we are using, and what is still required to make it enterprise-ready.

**Project name:** ErgoVigilance  
**Domain:** Industrial ergonomics, worker safety, posture analysis, computer vision  
**Current stage:** Strong prototype / pilot-ready candidate, but not fully enterprise-ready yet  
**Main repository areas referred:** `README.md`, `docs/CURRENT_STATE.md`, `docs/DELIVERY_CHECKLIST.md`, `docs/SYSTEM_ARCHITECTURE_PRESENTATION.md`, `docs/PRIVACY.md`, `ROADMAP.md`, `backend/`, `backend_api/`, `ui_posture/`, `yolo_cloud/`, `results/ground_truth_evaluation.json`

---

## 1. Simple Explanation of the Product

ErgoVigilance is an AI-based industrial ergonomics platform.

In simple words, it uses a camera to watch a worker's posture while they are doing a task, such as lifting, reaching, inspection, assembly, or seated work. The system detects the worker's body joints, calculates body angles like neck bend, trunk bend, shoulder elevation, knee angle, and wrist movement, and then converts these measurements into ergonomic risk levels.

The output is not only a skeleton on the screen. The product also gives:

- live risk level: LOW, MEDIUM, or HIGH
- alerts when risky posture continues for some time
- recommendations for the worker or supervisor
- session history
- reports in PDF, CSV, and JSON
- worker and manager dashboards
- video replay with skeleton overlay
- privacy and consent-related worker identity controls

The idea is to help factories reduce musculoskeletal injury risk before it becomes a serious problem.

---

## 2. Problem We Are Trying to Solve

In factories, warehouses, assembly lines, and industrial workplaces, workers often repeat the same body movements for many hours. A worker may bend the neck, twist the trunk, lift with poor posture, reach too far, or keep one shoulder elevated for a long time.

These small posture problems may not look dangerous in one moment, but over weeks and months they can lead to:

- back pain
- neck pain
- shoulder strain
- wrist strain
- knee stress
- fatigue
- reduced productivity
- workplace injury claims
- safety compliance issues

Today, many factories still depend on manual ergonomic audits. A safety officer may observe workers occasionally and fill a form like RULA or REBA. This is useful, but it has limitations:

- it is not continuous
- it depends on the observer's timing
- risky posture may happen when nobody is watching
- paper reports do not give real-time alerts
- supervisors cannot easily compare risk across workers, stations, or shifts

ErgoVigilance tries to solve this by turning posture assessment into a continuous, camera-based, evidence-backed system.

---

## 3. Main Vision

The long-term vision is:

> A factory should be able to use existing cameras or webcams to monitor ergonomic posture risk in real time, alert supervisors when risk is high, generate safety reports automatically, and help workers correct posture before injury happens.

This should be done in a responsible way:

- no wearable device should be required
- the system should be understandable, not a black box
- workers should know what is being monitored
- video should not leave the local machine by default
- privacy, consent, and data retention must be designed seriously

---

## 4. Who Will Use This Product?

### 4.1 Worker / Operator

The worker needs simple feedback:

- Is my posture okay?
- Am I bending too much?
- Should I adjust my position?
- Did my risk increase during this session?

For the worker, the product must use simple language. For example, instead of only saying "RULA score 5", it should say something like "Watch your back" or "High bending risk".

### 4.2 Supervisor

The supervisor wants to know:

- Which station has high risk right now?
- Which worker needs attention?
- Are alerts increasing today?
- Is a particular task causing repeated strain?

### 4.3 Safety Manager / EHS Manager

The safety manager needs:

- trend reports
- audit trail
- incident evidence
- risk comparison by worker, department, or shift
- PDF reports for compliance or management review

### 4.4 Admin / IT Person

The admin needs:

- user management
- worker management
- camera setup
- deployment health
- data retention settings
- authentication and access control

---

## 5. What the Product Does Today

Based on the current codebase and documentation, ErgoVigilance already has many working product parts.

### 5.1 Live Monitoring

The live monitoring screen takes camera input and processes frames through the posture pipeline. It can show:

- camera feed
- skeleton overlay
- risk level
- posture measurements
- task classification
- alerts
- recommendations
- live timeline

### 5.2 Pose Estimation

The system uses AI pose estimation to detect body landmarks. The on-premise core mainly uses MediaPipe Pose, which provides body keypoints. The cloud-oriented core uses YOLOv8-pose for camera/RTSP style input.

In simple words:

1. Camera captures frame.
2. Pose model detects body joints.
3. Code converts joints into angles and movement features.
4. Risk engine decides posture risk.
5. Dashboard displays the result.

### 5.3 Ergonomic Risk Scoring

The project does not only use a random machine learning prediction. It uses ergonomic logic inspired by standard assessment methods such as RULA and REBA.

The system measures body features such as:

- neck flexion
- trunk flexion
- shoulder elevation
- shoulder symmetry
- knee angle
- forward head posture
- head tilt
- wrist deviation
- stance stability
- weight shift
- wrist movement velocity
- general posture quality

Then it assigns risk levels using thresholds, task context, exposure duration, uncertainty, and smoothing.

This is important because a professor or safety expert can inspect and improve the rules. It is more explainable than a pure black-box model.

### 5.4 Alerts

The product can create alerts when posture risk remains high or crosses a threshold.

The alert lifecycle includes:

- alert created
- alert shown in UI
- alert acknowledged
- alert resolved
- alert stored for history/audit

### 5.5 Reports

The system can generate reports such as:

- session report
- risk trend report
- safety report
- worker trend report
- PDF export
- CSV/JSON export

This matters because industrial safety products must produce evidence, not only live screens.

### 5.6 Video Review and Replay

The project supports video analysis and replay.

This means a recorded video can be processed later, and the system can show:

- skeleton overlay on the video
- risk timeline
- frame-by-frame analysis
- risk distribution
- downloadable analyzed output

This is very useful for explaining the system to a professor because it makes the AI result visible and verifiable.

### 5.7 Worker Identity and Consent

The project has worker-related features:

- worker records
- employee IDs
- badge/QR identity
- face-related identity mode
- consent-aware design
- privacy deletion endpoint

The privacy document says the product is offline-first by default. Live frames are processed in memory, and raw frames are not stored unless recording is explicitly used.

### 5.8 Dashboards

The frontend has many routes/pages, including:

- landing page
- login
- dashboard
- live monitoring
- video review
- replay
- analytics
- session history
- reports
- workers
- users
- settings
- manager dashboard
- multi-camera view
- audit trail
- deployment center
- validation page
- pilot request page
- cloud camera pages
- model dashboard
- ROI analytics
- system health
- onboarding
- consent
- pricing/status pages

This shows the project is not just one Python script. It is shaped like a real product.

---

## 6. Technical Architecture

The project is divided into three main layers.

```text
Camera / Video
     |
     v
AI Core: pose estimation, feature extraction, risk scoring
     |
     v
FastAPI Backend: APIs, auth, sessions, reports, alerts
     |
     v
React Frontend: dashboards, live monitoring, reports, admin UI
```

### 6.1 `backend/` - AI Core

This is the computation layer. It contains the main posture intelligence.

Important responsibilities:

- pose processing
- feature extraction
- RULA/REBA-informed scoring
- task recognition
- recommendation engine
- alert engine
- history and trend analysis
- fatigue and exposure logic
- framing quality checks
- uncertainty-aware risk bands
- smoothing and prediction logic

This layer should ideally remain independent from HTTP and UI logic. That makes it easier to test, improve, and validate scientifically.

### 6.2 `backend_api/` - FastAPI Application

This is the API layer. It connects the AI core to the web application.

Important responsibilities:

- REST APIs
- WebSocket streams
- authentication using JWT
- role-based access control
- user and worker management
- sessions
- alerts
- reports
- video analysis jobs
- privacy endpoints
- health checks
- metrics
- retention
- settings
- audit log

This layer is what the frontend talks to.

### 6.3 `ui_posture/` - React Frontend

This is the user interface.

Important responsibilities:

- dashboard pages
- live monitoring page
- video review page
- reports page
- admin screens
- worker screens
- login and access flows
- charts and visualizations
- risk gauge
- alert center
- camera panels
- onboarding and setup pages

The frontend is built with React, TypeScript, Vite, Tailwind CSS, and chart components.

### 6.4 `yolo_cloud/` - Cloud / CCTV-Oriented Core

This is a second core focused on CCTV/RTSP and cloud-style deployment.

Important responsibilities:

- YOLOv8-pose inference
- RTSP camera ingestion
- tenant isolation
- API key authentication
- camera management
- cloud alerts
- webhooks
- report generation
- model versioning
- live WebSocket stream

This gives the project a possible SaaS direction in the future.

---

## 7. Data Flow in Detail

### 7.1 Live Monitoring Flow

```text
1. Camera captures the worker.
2. A frame is sent to the pose engine.
3. Pose engine finds body landmarks.
4. Feature extraction calculates angles and posture features.
5. Task recognition estimates the current work activity.
6. Ergonomic risk engine calculates LOW / MEDIUM / HIGH risk.
7. Alert engine checks whether risk is sustained enough to alert.
8. Recommendation engine gives practical guidance.
9. API sends data to frontend using HTTP/WebSocket.
10. Frontend shows live skeleton, risk gauge, charts, and alerts.
```

### 7.2 Recorded Video Flow

```text
1. User uploads or selects a video.
2. Backend creates a video analysis job.
3. Frames are processed through the same AI pipeline.
4. The system stores analysis results.
5. Frontend shows replay, skeleton overlay, and risk timeline.
6. User can export analyzed data or reports.
```

### 7.3 Reporting Flow

```text
1. Monitoring session ends.
2. Session summary is saved.
3. Risk percentages and posture statistics are calculated.
4. Reports page requests summaries from backend.
5. Backend generates PDF/CSV/JSON.
6. Safety manager downloads or reviews report.
```

---

## 8. Models and AI Approach

The project uses a hybrid AI approach.

### 8.1 Pose Detection

Pose detection is used to find human body joints from images or video frames.

On-premise:

- MediaPipe Pose
- 33 body landmarks
- suitable for CPU-based local demo

Cloud/CCTV direction:

- YOLOv8-pose
- RTSP camera input
- person detection and pose estimation
- useful for multiple cameras and industrial CCTV setups

### 8.2 Feature Engineering

The project does not directly say "the model says high risk" without explanation. It first converts body landmarks into features.

Examples:

- How much is the neck bent?
- How much is the trunk bent?
- Are shoulders raised?
- Is the worker leaning?
- Is the knee angle poor?
- Is the wrist moving fast?
- Is the camera view reliable?

This feature engineering is the bridge between computer vision and ergonomics.

### 8.3 Risk Scoring

Risk scoring is based on:

- RULA/REBA-informed ergonomic rules
- task-specific thresholds
- fatigue/exposure over time
- uncertainty in pose detection
- smoothing to avoid flickering risk levels

This is a good research direction because it is explainable and can be improved by ergonomic experts.

### 8.4 Machine Learning Classifiers

The project also has machine learning models for:

- task recognition
- risk calibration
- forecasting/prediction

However, we should be honest: the risk engine is still largely rule-based and ergonomics-informed, with ML support. We should not overclaim that the whole system is a clinically validated AI medical device.

---

## 9. Current Validation Evidence

The project has a ground-truth evaluation file: `results/ground_truth_evaluation.json`.

Current reported risk classification result:

- 500 matched human-labeled frames
- 87.6% overall accuracy
- LOW class: precision 1.0, recall about 57.2%
- MEDIUM class: precision about 85.1%, recall 100%

This means the system is conservative in one direction: it tends to catch MEDIUM risk well, but sometimes marks LOW frames as MEDIUM.

That behavior may be acceptable for a safety screening tool, because missing risk is usually worse than warning too early. But it can also cause alert fatigue if too many false warnings happen. This is an important area where professor guidance is valuable.

Important note:

Earlier inflated or circular accuracy claims were removed from the user-facing documentation. This is good engineering honesty. The current 87.6% number is more credible because it is based on human-labeled frames from real recordings.

---

## 10. Testing and Quality Status

According to the project documentation:

- backend test suite exists
- frontend smoke tests exist
- legacy script tests exist
- CI is described in the docs
- Docker runtime has been improved
- health endpoints exist
- readiness endpoints exist
- metrics endpoint exists
- retention policy exists
- privacy deletion endpoint exists
- model verification script exists

This is a strong sign that the project has moved beyond a one-screen demo.

Still, enterprise quality requires more than tests passing locally. We need repeated validation in real factory conditions.

---

## 11. Privacy and Responsible Design

This project monitors workers, so privacy is not optional.

The current design has several good privacy ideas:

- offline-first by default
- live video frames are processed in memory
- raw video is not stored unless recording is explicitly used
- reports are generated locally
- worker data deletion endpoint exists
- role-based access control exists
- audit logging exists
- consent-related worker identity design exists

For a real factory pilot, the project still needs:

- signed worker consent process
- visible notice/signage
- clear data retention policy
- admin access control
- backup and deletion policy
- legal review depending on the country and workplace rules

Professor guidance is very useful here because this project is not only technical. It involves human subjects, workplace monitoring, ethics, and compliance.

---

## 12. How Close Are We to Enterprise-Ready?

My honest assessment:

```text
Demo-ready:        85% to 90%
Pilot-ready:       70% to 80%
Enterprise-ready:  55% to 65%
```

### 12.1 Why Demo-Ready Is High

The product can be demonstrated well because it has:

- live monitoring UI
- pose skeleton overlay
- risk gauge
- reports
- session history
- video review
- demo mode
- dashboards
- validation page
- clear product story

For explaining to a professor or showing an MVP, this is strong.

### 12.2 Why Pilot-Ready Is Medium-High

The product has enough to attempt a controlled pilot if the scope is limited:

- one site
- one or few cameras
- clear consent
- supervised usage
- non-critical decision support only
- manual review of alerts
- feedback collection

But the pilot must be framed honestly:

> This is an ergonomic screening and decision-support tool, not a certified injury-prevention system.

### 12.3 Why Enterprise-Ready Is Still Not Complete

Enterprise-ready means a factory can depend on it every day with multiple users, cameras, shifts, and compliance expectations.

Remaining gaps:

- more real factory footage needed
- clinical/ergonomic validation needed
- multi-camera scaling needs field testing
- multi-person per-worker isolation is not fully finished
- task classifier needs more labeled real data
- long-running 24/7 reliability testing is needed
- backup and restore must be proven
- HTTPS/TLS deployment must be tested with real certs
- notification escalation needs real-world configuration
- mobile/tablet UX should be verified on factory devices
- privacy process must be approved by the organization

So the correct statement is:

> ErgoVigilance is a strong research/product prototype and close to a controlled factory pilot. It is not yet fully enterprise-ready, but the architecture is heading in that direction.

---

## 13. What Is Already Strong

### 13.1 Strong Product Scope

The project covers the full safety workflow:

- detect posture
- calculate risk
- alert
- recommend action
- save history
- generate reports
- manage workers
- support admin use

Many student projects stop after prediction. This project continues into product workflows.

### 13.2 Explainable Ergonomic Logic

The risk engine uses body features and RULA/REBA-informed thinking. This is better for professor review than a pure black box.

### 13.3 Real UI and Backend

There is a real React frontend and FastAPI backend. The project has routes, API modules, auth, dashboards, and reports.

### 13.4 Honest Validation Direction

The project includes human-labeled evaluation and admits limitations. This improves credibility.

### 13.5 Privacy Awareness

The project already discusses local processing, retention, consent, and deletion.

---

## 14. What Is Weak or Needs Improvement

### 14.1 More Real-World Data

The biggest scientific gap is data. We need more videos from different:

- workers
- body types
- camera angles
- lighting conditions
- clothing types
- tasks
- factory environments
- shift durations

Without this, we cannot claim strong generalization.

### 14.2 Better Task Recognition

Task recognition is harder than posture risk. A worker may look similar while doing different tasks. The task classifier needs more labeled clips and better evaluation.

### 14.3 Multi-Person Tracking

The product direction includes multiple workers, but fully reliable per-worker tracking and analytics is still a follow-up area.

The system may detect multiple people or report person count, but enterprise use needs:

- stable worker identity over time
- separate risk timelines per worker
- occlusion handling
- re-identification after leaving and returning
- fair handling when two people overlap

### 14.4 Field Reliability

Factory conditions are difficult:

- dust
- glare
- low light
- camera vibration
- workers partially hidden
- PPE and uniforms
- machinery occluding the body
- network instability
- power interruptions

We need 24/7 style testing before enterprise claims.

### 14.5 Formal Ergonomic Validation

RULA and REBA are known ergonomic methods, but our implementation and thresholds must be reviewed by ergonomics experts.

Questions:

- Are the calculated angles correct enough?
- Are risk bands aligned with real ergonomic judgment?
- Does the system over-alert?
- Does it miss dangerous postures?
- Should thresholds differ by task, worker height, workstation, or load?

This is exactly where professor guidance can help.

---

## 15. Suggested Explanation to Professor

You can explain it like this:

> Sir, this project is called ErgoVigilance. It is an AI-based industrial ergonomics platform. The goal is to detect risky worker posture using a normal camera and help prevent musculoskeletal injuries. The system detects body joints using computer vision, calculates ergonomic features like neck bend, trunk bend, shoulder elevation, knee angle, and wrist movement, and then uses RULA/REBA-inspired logic to classify risk as LOW, MEDIUM, or HIGH.
>
> It is not only a model. We built it like a product. There is a React dashboard, FastAPI backend, live monitoring, alerts, session history, reports, video review, worker management, privacy controls, and deployment files. The system has been evaluated on 500 human-labeled frames and currently shows 87.6% risk classification accuracy. We are treating this honestly as a screening and decision-support tool, not a certified medical or safety device.
>
> What we need guidance on now is validation and enterprise readiness: how to collect better factory data, how to compare our scoring with expert ergonomic assessment, how to reduce false alerts, how to improve task recognition, and how to design a proper pilot study with consent and privacy.

---

## 16. Product Modules Explained Simply

### 16.1 Camera Module

Purpose: capture live frames or receive video/RTSP stream.

Needs to handle:

- webcam
- IP camera
- RTSP camera
- camera reconnect
- camera setup and framing

### 16.2 Pose Module

Purpose: find the worker's body points.

Example points:

- nose
- shoulders
- elbows
- wrists
- hips
- knees
- ankles

### 16.3 Feature Module

Purpose: convert body points into useful ergonomic measurements.

Examples:

- neck angle
- trunk angle
- shoulder angle
- knee angle
- wrist deviation
- stance balance

### 16.4 Risk Engine

Purpose: decide how risky the posture is.

Inputs:

- body angles
- task type
- posture duration
- movement
- uncertainty
- fatigue/exposure

Output:

- LOW
- MEDIUM
- HIGH
- explanation/reasons

### 16.5 Alert Engine

Purpose: avoid silent danger.

It should not alert for every one-frame mistake. It should alert when risk is meaningful and sustained.

### 16.6 Recommendation Engine

Purpose: give useful next action.

Examples:

- adjust workstation height
- reduce forward bending
- bring object closer
- take micro-break
- rotate task
- inspect camera framing

### 16.7 Session Engine

Purpose: save what happened during one monitoring period.

Stores:

- duration
- average risk
- risk percentages
- alerts
- summary statistics
- optional recording references

### 16.8 Reporting Engine

Purpose: make the system useful for supervisors and audits.

Reports answer:

- What happened?
- Who/which station was at risk?
- When did risk increase?
- What action was recommended?
- Is risk improving over time?

### 16.9 Admin and Privacy Module

Purpose: make it acceptable in a real workplace.

Includes:

- users
- roles
- workers
- consent
- audit logs
- retention
- deletion

---

## 17. Proposed Development Roadmap

### Phase 1: Professor Review and Technical Cleanup

Goal: make the project easy to understand and review.

Tasks:

- review this document with professor
- demonstrate live monitoring and video review
- identify scientific weak points
- confirm ergonomic scoring assumptions
- document which rules are RULA/REBA-based and which are custom
- remove any outdated or conflicting claims from old docs

### Phase 2: Dataset and Validation

Goal: make the system scientifically credible.

Tasks:

- collect more real videos
- label more frames with ergonomic categories
- compare system output against human/expert labels
- calculate confusion matrix for LOW/MEDIUM/HIGH
- measure false positives and false negatives
- test different camera angles and lighting
- publish validation report

### Phase 3: Controlled Pilot

Goal: test in a real or realistic workplace setting.

Tasks:

- choose one workstation
- set up one camera
- get consent
- run for limited sessions
- collect alerts and reports
- ask worker/supervisor feedback
- check if alerts are useful or annoying
- tune thresholds

### Phase 4: Product Hardening

Goal: make it reliable for daily use.

Tasks:

- test long-running sessions
- test crash recovery
- test backup and restore
- test HTTPS/TLS deployment
- improve tablet responsiveness
- improve multi-camera view
- add notification escalation
- improve reports

### Phase 5: Enterprise Readiness

Goal: make it deployable in serious industrial environments.

Tasks:

- multi-site architecture decision
- multi-camera scaling
- stable per-worker tracking
- production database setup
- monitoring and logging stack
- security review
- privacy/legal review
- formal deployment guide
- support and maintenance process

---

## 18. Questions for Professor Guidance

### Ergonomics Questions

1. Are our measured features enough for ergonomic risk screening?
2. Should we use RULA, REBA, OWAS, or a combination?
3. Which postures are most important for factory injury prevention?
4. How should we handle task-specific thresholds?
5. What is an acceptable false alert rate?

### Computer Vision Questions

1. How should we validate angle accuracy from camera keypoints?
2. How do we handle side-view vs front-view posture?
3. How much camera calibration is necessary?
4. How do we handle occlusion and PPE?
5. Should we use MediaPipe, YOLOv8-pose, or both?

### Machine Learning Questions

1. How many labeled frames/clips are enough for a credible study?
2. Should task recognition be frame-based or sequence-based?
3. Should we use temporal models for movement tasks?
4. How do we avoid training on biased or narrow data?
5. How should we report accuracy honestly?

### Product and Deployment Questions

1. What minimum features are required for a factory pilot?
2. What should be excluded from the first pilot to reduce risk?
3. How should we present the product without overclaiming?
4. What documentation is needed before deployment?
5. What privacy and consent workflow is acceptable?

---

## 19. Enterprise Readiness Checklist

### Already Present or Mostly Present

- React frontend
- FastAPI backend
- live posture monitoring
- pose estimation
- risk scoring
- alert lifecycle
- session history
- reports
- video review
- worker management
- user roles
- JWT authentication
- audit trail
- privacy document
- retention policy
- Docker/deployment files
- health endpoints
- metrics endpoint
- validation page
- automated tests
- demo mode

### Needs More Work

- real factory pilot validation
- more human-labeled dataset
- stronger task recognition
- full multi-person tracking
- proven multi-camera scaling
- 24/7 reliability testing
- production backup and restore
- real HTTPS/TLS deployment test
- mobile/tablet usability testing
- notification escalation in real customer environment
- external security review
- legal/privacy approval
- formal user manual
- formal admin manual
- formal incident response process

---

## 20. Risks If We Overclaim

We should not say:

- "This prevents all injuries."
- "This is clinically certified."
- "This is fully enterprise-ready."
- "This works for every factory."
- "This accuracy is universal."
- "This replaces safety officers."

We can safely say:

- "This is an AI-assisted ergonomic risk screening system."
- "It detects posture features and gives real-time risk feedback."
- "It uses RULA/REBA-informed logic."
- "It has shown 87.6% accuracy on our current 500-frame human-labeled evaluation."
- "It is ready for controlled pilot evaluation."
- "It needs more field validation before enterprise claims."

This honest framing will make the project more credible, not weaker.

---

## 21. Recommended Next 30 Days

### Week 1

- Review scoring method with professor.
- Prepare a short demo: live monitoring, video review, report.
- Clean outdated documentation claims.
- Decide exactly what pilot scenario to test.

### Week 2

- Collect more real videos.
- Label frames and task clips.
- Re-run evaluation.
- Compare system scoring against human labels.

### Week 3

- Improve false positives and false negatives.
- Tune thresholds.
- Improve task recognition.
- Test camera angles and lighting.

### Week 4

- Run a small controlled pilot.
- Generate final pilot report.
- Document limitations.
- Define enterprise architecture plan.

---

## 22. Final Honest Summary

ErgoVigilance is a strong and ambitious project. It is no longer just a basic posture detection demo. It has a real product structure: frontend, backend, AI core, reports, alerts, sessions, identity, privacy, deployment, and validation.

The strongest part is the end-to-end workflow:

```text
camera -> pose -> features -> ergonomic risk -> alerts -> reports -> dashboard
```

The most important remaining work is validation. To become enterprise-ready, the system must be tested on more real factory data, reviewed by ergonomic experts, and proven in longer, messier, real-world conditions.

My honest conclusion:

> We are close to a controlled pilot and strong enough for professor review. We are not yet fully enterprise-ready, but we have built the right foundation. With expert validation, more real data, and production hardening, this can become a serious industrial ergonomics product.

