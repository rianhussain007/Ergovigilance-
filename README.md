# Ergonomic Posture Analysis System

Computer vision app for classifying ergonomic posture risk from images or a webcam feed.

## Tech Stack

- Pose detection: MediaPipe Pose / MediaPipe Tasks
- Classification: best of SVM and Random Forest on 6 pose features
- Backend: FastAPI
- Frontend: Streamlit
- Language: Python
- Runtime: Windows, local only

## Run The Project

1. Open PowerShell.
2. Go to the project folder:

```powershell
cd C:\GGS_intership\posture_analysis
```

3. Start the Streamlit app:

```powershell
.\run_frontend.bat
```

4. Open the local app:

```text
http://127.0.0.1:8501
```

5. Optional: start the API server in another terminal:

```powershell
.\run_backend.bat
```

6. API health check:

```text
http://127.0.0.1:8000/health
```

## App Features

- Image upload posture analysis
- Live webcam posture analysis
- LOW / MEDIUM / HIGH risk badge with recommendations
- Skeleton overlay with body-part risk colors
- PDF report download
- Saved annotated images in `results/`
- History dashboard from saved result metadata
- Edge-case handling for no person, low image quality, and partial-body visibility

## File Guide

- `frontend/app.py`: Streamlit UI, image upload, live camera, reports, history dashboard
- `backend/main.py`: FastAPI app with `POST /predict`
- `backend/services/features.py`: feature extraction, thresholds, risk helpers
- `backend/services/pose.py`: MediaPipe pose detection, image quality checks, skeleton annotation
- `scripts/build_dataset.py`: merges raw datasets into `data/processed/dataset_final.csv`
- `scripts/train_svm.py`: trains SVM and Random Forest, saves best model
- `models/best_model.pkl`: model used by the app/API
- `models/svm_model.pkl`: SVM model artifact
- `models/pose_landmarker_lite.task`: MediaPipe Tasks pose model
- `results/`: saved annotated images, JSON metadata, metrics, confusion matrix
- `notebooks/01_explore_datasets.ipynb`: raw dataset exploration
- `notebooks/02_feature_engineering.ipynb`: feature engineering and dataset build
- `notebooks/03_model_training.ipynb`: SVM vs Random Forest comparison, confusion matrix, per-class accuracy, feature importance

## Screenshots

### Image Upload
-[will be uploaded]

### Live Camera

-[will be uploaded]
### History Dashboard
-[will be uploaded]

## Model Training

To rebuild the dataset:

```powershell
.\venv\Scripts\python.exe scripts\build_dataset.py
```

To train and choose the best model:

```powershell
.\venv\Scripts\python.exe scripts\train_svm.py
```

The training script compares:

- SVM
- Random Forest

The higher-accuracy model is saved to:

```text
models/best_model.pkl
```

## Output Files

Each completed analysis saves:

- Annotated image: `results/result_YYYY-MM-DD_HH-MM-SS.jpg`
- Metadata: `results/result_YYYY-MM-DD_HH-MM-SS.json`
- Optional PDF report downloaded from the app

## Risk Thresholds

- Neck flexion: LOW <= 10 deg, MEDIUM 10-30 deg, HIGH > 30 deg
- Trunk flexion: LOW <= 20 deg, MEDIUM 20-60 deg, HIGH > 60 deg
- Shoulder elevation: LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg
- Shoulder symmetry: LOW <= 5%, MEDIUM 5-15%, HIGH > 15%
