"""Regression tests for the real-task capture scaffolding.

Covers the two pure functions the capture → dataset → train pipeline relies
on: folder-slug → canonical-label mapping (scripts/build_task_dataset.py) and
the CSV loader that feeds real samples into the trainer
(scripts/train_task_model_v2.py --data).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import scripts.build_task_dataset as builder  # noqa: E402
import scripts.train_task_model_v2 as trainer  # noqa: E402


class TestSlugMapping:
    def test_known_slugs_map_to_canonical_labels(self):
        assert builder._label_from_dir("neutral_standing") == "Neutral Standing"
        assert builder._label_from_dir("assembly_work") == "Assembly Work"
        assert builder._label_from_dir("lifting_picking") == "Lifting / Picking"
        assert builder._label_from_dir("reaching") == "Reaching"
        assert builder._label_from_dir("inspection") == "Inspection"

    def test_unknown_slug_falls_back_to_title_case(self):
        assert builder._label_from_dir("my_custom_task") == "My Custom Task"

    def test_train_features_are_the_model_contract(self):
        # The trainer's 19 features must be exactly what the builder writes.
        assert trainer.TRAIN_FEATURES == builder.TRAIN_FEATURES
        assert len(trainer.TRAIN_FEATURES) == 19


class TestLoadReal:
    def test_loads_known_labels_and_drops_unknown(self, tmp_path):
        import pandas as pd

        csv_path = tmp_path / "features.csv"
        pd.DataFrame([
            {"task_label": "Neutral Standing", **{f: 1.0 for f in trainer.TRAIN_FEATURES}},
            {"task_label": "Lifting / Picking", **{f: 2.0 for f in trainer.TRAIN_FEATURES}},
            {"task_label": "Not A Class", **{f: 3.0 for f in trainer.TRAIN_FEATURES}},
        ]).to_csv(csv_path, index=False)

        X, y, stats = trainer.load_real(csv_path)
        assert len(X) == 2
        assert sorted(y) == ["Lifting / Picking", "Neutral Standing"]
        assert stats["per_class"]["Neutral Standing"] == 1
        assert X[0][0] == 1.0  # NaN-free float rows in the model's feature order

    def test_empty_or_unknown_only_raises(self, tmp_path):
        import pandas as pd

        csv_path = tmp_path / "empty.csv"
        pd.DataFrame(columns=["task_label", *trainer.TRAIN_FEATURES]).to_csv(csv_path, index=False)
        with pytest.raises(RuntimeError):
            trainer.load_real(csv_path)
