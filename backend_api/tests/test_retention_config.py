"""Regression tests for the persisted retention policy override layer."""

import os
import tempfile
import unittest
from unittest import mock

from app.services.retention import _load_overrides, retention_config, set_retention_config


class RetentionConfigOverrideTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._path = os.path.join(self._tmp.name, "retention.json")
        # Deterministic baseline: clear retention env vars so the tests only
        # exercise the override file (the CI/dev shell may set these to 0).
        self._env = mock.patch.dict(
            os.environ,
            {
                "SESSION_RETENTION_DAYS": "",
                "RECORDING_RETENTION_DAYS": "",
                "RECORDINGS_MAX_GB": "",
            },
            clear=False,
        )
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def test_no_override_file_uses_env_defaults(self):
        with mock.patch("app.services.retention._OVERRIDE_PATH", self._path):
            with mock.patch.dict(os.environ, {}, clear=True):
                cfg = retention_config()
        self.assertEqual(cfg["session_retention_days"], 30)
        self.assertEqual(cfg["recording_retention_days"], 30)
        self.assertEqual(cfg["recordings_max_gb"], 20)

    def test_set_persists_and_layers(self):
        with mock.patch("app.services.retention._OVERRIDE_PATH", self._path):
            merged, persisted = set_retention_config({"session_retention_days": 60})
            self.assertTrue(persisted)
            self.assertEqual(merged["session_retention_days"], 60)
            # Unspecified keys keep the current effective value.
            self.assertEqual(merged["recording_retention_days"], 30)

            cfg = retention_config()
            self.assertEqual(cfg["session_retention_days"], 60)
            self.assertEqual(cfg["recording_retention_days"], 30)

    def test_partial_update_merges_with_existing(self):
        with mock.patch("app.services.retention._OVERRIDE_PATH", self._path):
            set_retention_config({"session_retention_days": 60, "recordings_max_gb": 10})
            merged, _ = set_retention_config({"session_retention_days": 90})
            self.assertEqual(merged["session_retention_days"], 90)
            self.assertEqual(merged["recordings_max_gb"], 10)
            self.assertEqual(merged["recording_retention_days"], 30)

    def test_unwritable_path_reports_not_persisted(self):
        missing_dir = os.path.join(self._tmp.name, "nope", "sub", "retention.json")
        with mock.patch("app.services.retention._OVERRIDE_PATH", missing_dir):
            # Directory chain is creatable, so force a failure via a file-as-dir.
            blocker = os.path.join(self._tmp.name, "nope")
            with open(blocker, "w") as f:
                f.write("block")
            merged, persisted = set_retention_config({"session_retention_days": 90})
            self.assertFalse(persisted)
            self.assertEqual(merged["session_retention_days"], 90)

    def test_corrupt_override_file_ignored(self):
        with open(self._path, "w") as f:
            f.write("{not json")
        with mock.patch("app.services.retention._OVERRIDE_PATH", self._path):
            self.assertEqual(_load_overrides(), {})
            cfg = retention_config()
            self.assertEqual(cfg["session_retention_days"], 30)


if __name__ == "__main__":
    unittest.main()
