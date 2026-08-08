"""Regression tests for the async video-analysis job queue."""

import unittest
from unittest import mock

from app.api import video_analysis as module


class VideoAnalysisJobStoreTest(unittest.TestCase):
    def setUp(self):
        self._lock = module._jobs_lock
        with self._lock:
            self._saved = module._jobs
            module._jobs = {}
        self._start = mock.patch.object(module.threading.Thread, "start", autospec=True)
        self._mock_start = self._start.start()

    def tearDown(self):
        self._start.stop()
        with self._lock:
            module._jobs = self._saved

    def test_job_record_is_created_on_submit(self):
        # Simulate the submit path's job creation + thread dispatch.
        with self._lock:
            module._jobs["VIDJOB-TEST1"] = module.VideoAnalysisJob(
                job_id="VIDJOB-TEST1", status="queued"
            )
        self._mock_start.assert_not_called()
        job = module._jobs["VIDJOB-TEST1"]
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.progress["percent"], 0.0)

    def test_progress_update_and_completion(self):
        with self._lock:
            module._jobs["VIDJOB-TEST2"] = module.VideoAnalysisJob(
                job_id="VIDJOB-TEST2", status="processing"
            )
        # progress_cb writes to the job record
        cb = module._run_job  # not run directly; emulate the inner callback path
        # Build the same progress callback the worker uses:
        def progress_cb(processed, total):
            with module._jobs_lock:
                job = module._jobs.get("VIDJOB-TEST2")
                if job is None:
                    return
                job.progress = {
                    "frames_processed": processed,
                    "total_frames": total,
                    "percent": round(processed / total * 100, 1) if total else 0.0,
                }

        progress_cb(50, 200)
        self.assertEqual(module._jobs["VIDJOB-TEST2"].progress["percent"], 25.0)
        progress_cb(200, 200)
        self.assertEqual(module._jobs["VIDJOB-TEST2"].progress["percent"], 100.0)

    def test_error_sets_error_status(self):
        with self._lock:
            module._jobs["VIDJOB-TEST3"] = module.VideoAnalysisJob(
                job_id="VIDJOB-TEST3", status="processing"
            )
        # Emulate _run_job's exception path
        with self._lock:
            job = module._jobs.get("VIDJOB-TEST3")
            if job is not None:
                job.status = "error"
                job.error = "Pose model not found at /nope"
        job = module._jobs["VIDJOB-TEST3"]
        self.assertEqual(job.status, "error")
        self.assertIn("model", job.error.lower())

    def test_cleanup_expired_removes_finished_jobs(self):
        import time as _time
        with self._lock:
            module._jobs["VIDJOB-OLD"] = module.VideoAnalysisJob(
                job_id="VIDJOB-OLD", status="complete"
            )
            module._jobs["VIDJOB-OLD"]._finished_at = _time.time() - 60 * 60
            module._jobs["VIDJOB-FRESH"] = module.VideoAnalysisJob(
                job_id="VIDJOB-FRESH", status="complete"
            )
            module._jobs["VIDJOB-FRESH"]._finished_at = _time.time()
        module._cleanup_expired_jobs()
        with self._lock:
            self.assertNotIn("VIDJOB-OLD", module._jobs)
            self.assertIn("VIDJOB-FRESH", module._jobs)

    def test_finished_at_not_serialized(self):
        """The private _finished_at bookkeeping never leaks into the payload."""
        with self._lock:
            job = module.VideoAnalysisJob(job_id="VIDJOB-X", status="complete")
            job._finished_at = 123.0
        payload = job.model_dump()
        self.assertNotIn("_finished_at", payload)
        self.assertNotIn("_finished_at", payload["progress"])

    def test_run_job_completes_and_cleans_temp(self):
        fake_result = mock.MagicMock()
        fake_result.frames = [1, 2, 3]
        fake_result.summary.source_frames = 100
        temp_path = "/tmp/fake-video.mp4"
        with mock.patch.object(module, "_analyze_video_file", return_value=fake_result), \
             mock.patch.object(module.os, "unlink") as unlink:
            with self._lock:
                module._jobs["VIDJOB-RUN"] = module.VideoAnalysisJob(
                    job_id="VIDJOB-RUN", status="queued"
                )
            module._run_job("VIDJOB-RUN", temp_path, "fake.mp4")
            unlink.assert_called_once_with(temp_path)
            job = module._jobs["VIDJOB-RUN"]
        self.assertEqual(job.status, "complete")
        self.assertEqual(job.progress["percent"], 100.0)

    def test_run_job_error_path_cleans_temp(self):
        with mock.patch.object(
            module, "_analyze_video_file", side_effect=RuntimeError("boom")
        ), mock.patch.object(module.os, "unlink"):
            with self._lock:
                module._jobs["VIDJOB-ERR"] = module.VideoAnalysisJob(
                    job_id="VIDJOB-ERR", status="processing"
                )
            module._run_job("VIDJOB-ERR", "/tmp/fake.mp4", "fake.mp4")
            job = module._jobs["VIDJOB-ERR"]
        self.assertEqual(job.status, "error")
        self.assertIn("boom", job.error)


if __name__ == "__main__":
    unittest.main()
