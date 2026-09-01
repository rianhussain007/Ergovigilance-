"""YOLO Cloud Core — Model Registry.

Handles model versioning, export/import, and lifecycle management.
Each training run creates a versioned snapshot that can be rolled back
or exported for deployment on another machine.

Usage:
    from yolo_cloud.model_registry import ModelRegistry
    registry = ModelRegistry()
    
    # Export current models as a zip
    zip_path = registry.export_models()
    
    # Import models from a zip
    registry.import_models(zip_path)
    
    # List all versions
    versions = registry.list_versions()
    
    # Rollback to a previous version
    registry.rollback(version_id="20260831_225300")
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Default paths
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
REGISTRY_DIR = MODELS_DIR / ".registry"

# Model files to track
YOLO_MODEL_FILES = [
    "yolo_risk_model.pkl",
    "yolo_task_model.pkl",
    "yolo_risk_metrics.json",
    "yolo_task_metrics.json",
]


@dataclass
class ModelVersion:
    """A versioned snapshot of trained models."""
    version_id: str
    timestamp: str
    description: str = ""
    metrics: dict = field(default_factory=dict)
    files: list[str] = field(default_factory=list)


class ModelRegistry:
    """Manages model versioning, export, and import."""

    def __init__(self, models_dir: Path = MODELS_DIR, registry_dir: Path = REGISTRY_DIR):
        self.models_dir = models_dir
        self.registry_dir = registry_dir
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    def save_version(self, description: str = "") -> ModelVersion:
        """Snapshot current models as a new version."""
        version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_dir = self.registry_dir / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        # Copy model files
        copied_files = []
        for fname in YOLO_MODEL_FILES:
            src = self.models_dir / fname
            if src.exists():
                shutil.copy2(src, version_dir / fname)
                copied_files.append(fname)

        # Load metrics for the version metadata
        metrics = {}
        for fname in YOLO_MODEL_FILES:
            if fname.endswith("_metrics.json"):
                src = self.models_dir / fname
                if src.exists():
                    with open(src) as f:
                        metrics[fname.replace("_metrics.json", "")] = json.load(f)

        version = ModelVersion(
            version_id=version_id,
            timestamp=datetime.now().isoformat(),
            description=description,
            metrics=metrics,
            files=copied_files,
        )

        # Save version manifest
        manifest_path = version_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({
                "version_id": version_id,
                "timestamp": version.timestamp,
                "description": description,
                "metrics": metrics,
                "files": copied_files,
            }, f, indent=2)

        return version

    def list_versions(self) -> list[ModelVersion]:
        """List all saved model versions."""
        versions = []
        for version_dir in sorted(self.registry_dir.iterdir(), reverse=True):
            manifest_path = version_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    data = json.load(f)
                versions.append(ModelVersion(**data))
        return versions

    def rollback(self, version_id: str) -> bool:
        """Restore models from a specific version."""
        version_dir = self.registry_dir / version_id
        if not version_dir.exists():
            return False

        for fname in YOLO_MODEL_FILES:
            src = version_dir / fname
            if src.exists():
                shutil.copy2(src, self.models_dir / fname)

        return True

    def export_models(self, output_path: Optional[Path] = None) -> Path:
        """Export current models as a downloadable zip file.

        The zip contains:
        - All .pkl model files
        - All _metrics.json files
        - manifest.json with version info
        """
        if output_path is None:
            output_path = self.models_dir / f"yolo_models_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in YOLO_MODEL_FILES:
                fpath = self.models_dir / fname
                if fpath.exists():
                    zf.write(fpath, fname)

            # Add current metrics summary
            summary = {
                "exported_at": datetime.now().isoformat(),
                "models": {},
            }
            for fname in YOLO_MODEL_FILES:
                if fname.endswith("_metrics.json"):
                    fpath = self.models_dir / fname
                    if fpath.exists():
                        with open(fpath) as f:
                            summary["models"][fname.replace("_metrics.json", "")] = json.load(f)

            zf.writestr("export_manifest.json", json.dumps(summary, indent=2))

        return output_path

    def import_models(self, zip_path: Path) -> dict:
        """Import models from a zip file.

        Returns a dict with the import results.
        """
        if not zip_path.exists():
            raise FileNotFoundError(f"Zip not found: {zip_path}")

        imported = []
        skipped = []

        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".pkl"):
                    # Extract to models directory
                    zf.extract(name, self.models_dir)
                    imported.append(name)
                elif name.endswith("_metrics.json"):
                    zf.extract(name, self.models_dir)
                    imported.append(name)
                elif name == "export_manifest.json":
                    # Save as import record
                    manifest_data = json.loads(zf.read(name))
                    import_record = self.models_dir / ".registry" / f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(import_record, "w") as f:
                        json.dump(manifest_data, f, indent=2)
                    imported.append(name)
                else:
                    skipped.append(name)

        # Save a version snapshot of the imported models
        version = self.save_version(description=f"Imported from {zip_path.name}")

        return {
            "imported": imported,
            "skipped": skipped,
            "version_id": version.version_id,
        }

    def get_current_metrics(self) -> dict:
        """Get current model metrics."""
        metrics = {}
        for fname in YOLO_MODEL_FILES:
            if fname.endswith("_metrics.json"):
                fpath = self.models_dir / fname
                if fpath.exists():
                    with open(fpath) as f:
                        metrics[fname.replace("_metrics.json", "")] = json.load(f)
        return metrics
