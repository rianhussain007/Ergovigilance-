"""Track → worker identity binding for the YOLO cloud core.

A camera-level ``track_id`` is anonymous and ephemeral; this module attaches a
stable ``worker_id`` to it through two paths, in order of trust:

  * **badge / QR scan** — an explicit operator action binds ``track_id`` to a
    ``worker_id``. Re-scanning is allowed and each rebind is counted/logged as
    an ID switch (a worker leaves and another takes the same seat).
  * **face match** — only for workers who granted consent *and* chose
    ``identity_mode='face'``. This reuses the on-premise ``worker_faces``
    recognizer, so match thresholds and the verified/unverified bands stay
    identical to the MediaPipe core. Matches below the verified band are never
    bound — a safety product that guesses names is worse than one that says
    "unknown".

Withdrawing consent unbinds every live track for that worker and erases their
biometric samples, and is latched locally so face matching cannot rebind them
even when the shared database is unavailable (file mode).

Bindings are in-memory and scoped to ``(camera_id, track_id)``: they are live
state, not history. The per-track timeline in ``ingestion`` records the
``worker_id`` that was bound at each sample, so history survives a restart via
the session payload.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from yolo_cloud import identity_audit as audit

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iou_xyxy(a, b) -> float:
    """IoU of two ``[x1, y1, x2, y2]`` boxes (both in the same space)."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area > 0 else 0.0


class TrackIdentityRegistry:
    """Live ``(camera_id, track_id) -> worker_id`` bindings.

    Thread-safe: the ingestion processors and the API run on different threads.
    """

    # A worker must reappear within this window, and the new box must overlap the
    # remembered one, for a re-entry re-attach to be considered.
    REENTRY_WINDOW_S = float(os.getenv("IDENTITY_REENTRY_WINDOW_S", "120"))
    REENTRY_IOU = float(os.getenv("IDENTITY_REENTRY_IOU", "0.3"))

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # camera_id -> {track_id: binding}
        self._by_camera: dict[str, dict[int, dict]] = {}
        self._revoked: set[str] = set()
        self._switches: dict[str, int] = {}
        self.id_switch_count = 0
        # (camera_id, worker_id) -> last seen box, so a worker who leaves the
        # frame and comes back (track ids are never reused) can be re-attached.
        self._recent: dict[tuple[str, str], dict] = {}
        self.reentry_count = 0
        self.reentry_ambiguous_count = 0

    # ── reads ────────────────────────────────────────────────────────────
    def binding_for(self, camera_id: str, track_id: int) -> Optional[str]:
        with self._lock:
            rec = self._by_camera.get(camera_id, {}).get(int(track_id))
            return rec.get("worker_id") if rec else None

    def binding_record(self, camera_id: str, track_id: int) -> Optional[dict]:
        with self._lock:
            rec = self._by_camera.get(camera_id, {}).get(int(track_id))
            return dict(rec) if rec else None

    def bindings_for_camera(self, camera_id: str) -> dict[int, dict]:
        with self._lock:
            return {t: dict(r) for t, r in self._by_camera.get(camera_id, {}).items()}

    def is_revoked(self, worker_id: str) -> bool:
        with self._lock:
            return worker_id in self._revoked

    def switch_count(self, camera_id: Optional[str] = None) -> int:
        """ID switches seen so far (total, or for one camera)."""
        with self._lock:
            if camera_id is None:
                return self.id_switch_count
            return self._switches.get(camera_id, 0)

    # ── writes ───────────────────────────────────────────────────────────
    def bind(
        self,
        camera_id: str,
        track_id: int,
        worker_id: str,
        *,
        method: str,
        confidence: float = 1.0,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        bbox=None,
    ) -> dict:
        """Bind ``track_id`` to ``worker_id``. Returns the binding record.

        A rebind to a *different* worker on the same track is counted and
        logged as an ID switch (seat hand-over). Every bind/rebind is written to
        the append-only identity audit log with its actor and reason.
        """
        track_id = int(track_id)
        switched = False
        with self._lock:
            cam = self._by_camera.setdefault(camera_id, {})
            prev = cam.get(track_id)
            if prev is not None and prev.get("worker_id") != worker_id:
                switched = True
                self.id_switch_count += 1
                self._switches[camera_id] = self._switches.get(camera_id, 0) + 1
            rec = {
                "camera_id": camera_id,
                "track_id": track_id,
                "worker_id": worker_id,
                "method": method,
                "confidence": round(float(confidence), 3),
                "bound_at": _now_iso(),
                "actor": actor,
                "reason": reason,
                "previous_worker_id": prev.get("worker_id") if switched else None,
            }
            cam[track_id] = rec
            if bbox is not None:
                self._recent[(camera_id, worker_id)] = {
                    "track_id": track_id,
                    "bbox": [float(v) for v in bbox],
                    "at": time.time(),
                }
        audit.record(
            "rebind" if switched else "bind",
            camera_id=camera_id, track_id=track_id, worker_id=worker_id,
            method=method, actor=actor, reason=reason,
            confidence=rec["confidence"], previous_worker_id=rec["previous_worker_id"],
        )
        if switched:
            logger.warning(
                "ID switch: camera=%s track=%d worker %s -> %s (total switches=%d)",
                camera_id, track_id, prev.get("worker_id"), worker_id,
                self.id_switch_count,
            )
        else:
            logger.info(
                "Identity bound: camera=%s track=%d worker=%s via %s",
                camera_id, track_id, worker_id, method,
            )
        return rec

    def unbind(self, camera_id: str, track_id: int,
               actor: Optional[str] = None, reason: Optional[str] = None) -> bool:
        with self._lock:
            cam = self._by_camera.get(camera_id, {})
            removed = cam.pop(int(track_id), None)
        if removed is not None:
            audit.record("unbind", camera_id=camera_id, track_id=int(track_id),
                         worker_id=removed.get("worker_id"),
                         method=removed.get("method"), actor=actor, reason=reason)
        return removed is not None

    def bind_badge(self, camera_id: str, track_id: int, worker_id: str,
                   actor: Optional[str] = None, bbox=None) -> dict:
        """Badge/QR scan binding — the PRIMARY identity path.

        An explicit scan always outranks a probabilistic face match, so this
        replaces any existing identity (badge or face) on the track, and it is
        never blocked by the face-consent gate.
        """
        if not worker_id:
            return {"bound": False, "reason": "worker_id_required"}
        return {
            "bound": True,
            **self.bind(camera_id, track_id, worker_id, method="badge",
                        actor=actor, bbox=bbox),
        }

    def override(self, camera_id: str, track_id: int, worker_id: str,
                 supervisor: str, reason: str = "") -> dict:
        """Supervisor override — force a binding regardless of badge/face state.

        Deliberately bypasses the consent gate (a supervisor correcting a
        mis-read badge on the floor must not be blocked by the recognizer), so a
        reason is strongly expected and the event is always audited with the
        actor.
        """
        if not worker_id:
            return {"bound": False, "reason": "worker_id_required"}
        if not supervisor:
            return {"bound": False, "reason": "supervisor_required"}
        rec = self.bind(
            camera_id, track_id, worker_id, method="supervisor_override",
            confidence=1.0, actor=supervisor, reason=reason,
        )
        audit.record("override", camera_id=camera_id, track_id=int(track_id),
                     worker_id=worker_id, method="supervisor_override",
                     actor=supervisor, reason=reason)
        return {"bound": True, "override": True, **rec}

    def remember(self, camera_id: str, worker_id: str, track_id: int, bbox) -> None:
        """Remember a bound worker's current box (feeds re-entry re-attach).

        Called every frame from the ingestion loop, so the box is fresh even when
        the binding itself came from an API call that had no box to hand.
        """
        if bbox is None or not worker_id:
            return
        with self._lock:
            self._recent[(camera_id, worker_id)] = {
                "track_id": int(track_id),
                "bbox": [float(v) for v in bbox],
                "at": time.time(),
            }

    def try_rebind(self, camera_id: str, track_id: int, bbox) -> Optional[dict]:
        """Re-attach an identity to a NEW track_id after an exit/re-entry.

        Track ids are never reused, so a worker who walks out of frame and back
        gets a fresh id with no binding. If exactly ONE recently-seen identity in
        this camera overlaps the new box, re-attach it. Two or more candidates is
        ambiguous and is left unbound (logged, never guessed).
        """
        track_id = int(track_id)
        if bbox is None:
            return None
        with self._lock:
            if track_id in self._by_camera.get(camera_id, {}):
                return None
            now = time.time()
            cands = []
            for (cam, wid), rec in self._recent.items():
                if cam != camera_id or now - rec["at"] > self.REENTRY_WINDOW_S:
                    continue
                iou = _iou_xyxy(rec["bbox"], [float(v) for v in bbox])
                if iou >= self.REENTRY_IOU:
                    cands.append((iou, wid, rec))
            cands.sort(key=lambda c: c[0], reverse=True)
            if not cands:
                return None
            if len(cands) > 1:
                self.reentry_ambiguous_count += 1
                audit.record("reentry_ambiguous", camera_id=camera_id,
                             track_id=track_id, candidates=[c[1] for c in cands])
                return None
            iou, wid, rec = cands[0]
        self.reentry_count += 1
        audit.record("reentry", camera_id=camera_id, track_id=track_id,
                     worker_id=wid, method="reentry", confidence=round(iou, 3),
                     previous_track_id=rec.get("track_id"))
        logger.info("Re-entry re-bind: camera=%s track=%d worker=%s (iou=%.2f)",
                    camera_id, track_id, wid, iou)
        return self.bind(camera_id, track_id, wid, method="reentry",
                         confidence=iou, bbox=bbox)

    def bind_face(self, camera_id: str, track_id: int, embedding) -> dict:
        """Consent-gated face binding.

        Reuses the on-premise recognizer, whose candidate list already filters
        out workers with ``identity_mode != 'face'`` or ``consent_status ==
        'denied'``. Only *verified* matches (>= FACE_MATCH_THRESHOLD) bind.
        """
        with self._lock:
            already = self._by_camera.get(camera_id, {}).get(int(track_id))
        if already and already.get("method") == "badge":
            # An explicit scan outranks a probabilistic face match.
            return {"bound": False, "reason": "badge_binding_precedence",
                    "worker_id": already.get("worker_id")}

        identify_face = _load_identify_face()
        if identify_face is None:
            return {"bound": False, "reason": "face_recognizer_unavailable"}

        result = identify_face(embedding) or {}
        worker_id = result.get("worker_id")
        # Consent gate: the recognizer excludes non-consented workers, but never
        # trust a match for a worker we have locally latched as withdrawn.
        if worker_id and self.is_revoked(worker_id):
            audit.record("face_rejected", camera_id=camera_id, track_id=int(track_id),
                         worker_id=worker_id, method="face",
                         reason="consent_withdrawn")
            return {"bound": False, "reason": "consent_withdrawn", "worker_id": worker_id}

        if not result.get("verified"):
            audit.record("face_rejected", camera_id=camera_id, track_id=int(track_id),
                         worker_id=worker_id, method="face",
                         band=result.get("band"),
                         confidence=result.get("confidence", 0.0),
                         reason="below_match_threshold")
            return {
                "bound": False,
                "reason": "below_match_threshold",
                "band": result.get("band"),
                "worker_id": worker_id,
                "confidence": result.get("confidence", 0.0),
            }
        return {
            "bound": True,
            **self.bind(
                camera_id, track_id, worker_id,
                method="face", confidence=float(result.get("confidence", 0.0)),
            ),
        }

    def withdraw(self, worker_id: str) -> dict:
        """Unbind every live track for a worker and erase their biometrics.

        Also latches the worker so face matching cannot rebind them without an
        explicit re-consent (``restore``).
        """
        with self._lock:
            self._revoked.add(worker_id)
            removed = []
            for camera_id, cam in self._by_camera.items():
                for track_id in [t for t, r in cam.items() if r.get("worker_id") == worker_id]:
                    cam.pop(track_id, None)
                    removed.append({"camera_id": camera_id, "track_id": track_id})
        wiped = False
        delete_worker_face = _load_delete_worker_face()
        if delete_worker_face is not None:
            try:
                wiped = bool(delete_worker_face(worker_id))
            except Exception as exc:  # noqa: BLE001 - privacy route must not 500
                logger.warning("Biometric wipe failed for %s: %s", worker_id, exc)
        logger.warning(
            "Consent withdrawn: worker=%s unbound_tracks=%d biometrics_wiped=%s",
            worker_id, len(removed), wiped,
        )
        audit.record("consent_withdraw", worker_id=worker_id,
                     unbound_tracks=removed, unbound_count=len(removed),
                     biometrics_wiped=wiped, method="face")
        return {
            "worker_id": worker_id,
            "unbound_tracks": removed,
            "unbound_count": len(removed),
            "biometrics_wiped": wiped,
            "face_matching_disabled": True,
        }

    def restore(self, worker_id: str) -> dict:
        """Clear the local withdrawal latch (after the operator records new consent)."""
        with self._lock:
            self._revoked.discard(worker_id)
        audit.record("consent_restore", worker_id=worker_id, method="face")
        logger.info("Consent restored: worker=%s face matching re-enabled", worker_id)
        return {"worker_id": worker_id, "face_matching_disabled": False}

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "bindings": {
                    cam: {t: dict(r) for t, r in tracks.items()}
                    for cam, tracks in self._by_camera.items()
                },
                "revoked": sorted(self._revoked),
                "id_switch_count": self.id_switch_count,
                "id_switches_by_camera": dict(self._switches),
                "reentry_count": self.reentry_count,
                "reentry_ambiguous_count": self.reentry_ambiguous_count,
            }


def _load_identify_face():
    """Import the on-premise recognizer without hard-failing the cloud core."""
    for mod in ("backend_api.app.services.worker_faces", "backend.services.worker_faces"):
        try:
            import importlib

            return getattr(importlib.import_module(mod), "identify_face")
        except Exception:  # noqa: BLE001 - optional dependency
            continue
    logger.info("worker_faces recognizer unavailable — face identity disabled")
    return None


def embedding_from_image_bytes(image_bytes: bytes):
    """Compute a SFace embedding from raw image bytes via the on-premise
    recognizer, or None when face models/recognizer are unavailable."""
    embed = None
    for mod in ("backend_api.app.services.worker_faces", "backend.services.worker_faces"):
        try:
            import importlib

            embed = getattr(importlib.import_module(mod), "embedding_from_image")
            break
        except Exception:  # noqa: BLE001 - optional dependency
            continue
    if embed is None:
        return None
    try:
        return embed(image_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding extraction failed: %s", exc)
        return None


def _load_delete_worker_face():
    for mod in ("backend_api.app.services.worker_faces", "backend.services.worker_faces"):
        try:
            import importlib

            return getattr(importlib.import_module(mod), "delete_worker_face")
        except Exception:  # noqa: BLE001 - optional dependency
            continue
    return None


_registry: Optional[TrackIdentityRegistry] = None


def get_identity_registry() -> TrackIdentityRegistry:
    global _registry
    if _registry is None:
        _registry = TrackIdentityRegistry()
    return _registry
