"""Station ROI polygons — per-camera workstation boundaries.

A supervisor draws one polygon per workstation over a camera's stream; the pose
engine maps each track's ``bbox`` centroid to the station whose polygon contains
it, so a worker who moves between workstations is reported against the right one
instead of only being identified by ``track_id``.

Coordinates are **normalized to the frame (0..1)**, not pixels, so a boundary
drawn at one stream resolution keeps working if the stream size changes.

Storage is a single JSON file (offline-first, mirroring ``identity_audit``), so
station setup works with no database. ``storage.py`` carries the equivalent
PostgreSQL table for deployments that configure ``DATABASE_URL``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from yolo_cloud.config import settings

logger = logging.getLogger(__name__)

# Bumped when the on-disk shape changes in a way a reader must know about.
STORE_VERSION = 1

# A station is an area, so a polygon needs a triangle at minimum and real extent.
MIN_VERTICES = 3
MIN_AREA = 1e-6


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _xy(vertex) -> tuple[float, float]:
    """Read a vertex as ``(x, y)`` from either ``{"x": .., "y": ..}`` or a pair.

    A dict missing ``x`` or ``y`` is an error rather than a defaulted 0.0 — a
    silent 0.0 would move the vertex onto the frame edge instead of failing.
    """
    if isinstance(vertex, dict):
        if "x" not in vertex or "y" not in vertex:
            raise ValueError("vertex must have both 'x' and 'y'")
        return float(vertex["x"]), float(vertex["y"])
    return float(vertex[0]), float(vertex[1])


def polygon_area(polygon) -> float:
    """Absolute polygon area (shoelace formula). Independent of vertex order."""
    points = [_xy(v) for v in polygon]
    if len(points) < 3:
        return 0.0
    total = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def point_in_polygon(px: float, py: float, polygon) -> bool:
    """Ray-casting point-in-polygon test (PNPOLY).

    Counts edge crossings of a horizontal ray from ``(px, py)`` towards +x; an
    odd count means inside. Works for concave polygons and for either vertex
    order, so the UI can emit points clockwise or counter-clockwise.

    A point lying exactly on an edge or vertex follows the half-open convention
    and the result is then unspecified. Station polygons should not share edges,
    and a track centroid landing precisely on one is not a meaningful case.
    """
    points = [_xy(v) for v in polygon]
    if len(points) < 3:
        return False

    inside = False
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        # Half-open in y so a vertex is counted once, not twice.
        if (y1 > py) != (y2 > py):
            x_cross = (x2 - x1) * (py - y1) / (y2 - y1) + x1
            if px < x_cross:
                inside = not inside
    return inside


def normalize_polygon(polygon) -> list[dict]:
    """Validate and coerce a polygon to ``[{"x": float, "y": float}, ...]``.

    Raises ``ValueError`` with a message meant for the supervisor who drew it.
    """
    if not polygon:
        raise ValueError("polygon must contain at least 3 points")

    points: list[dict] = []
    for i, vertex in enumerate(polygon):
        try:
            x, y = _xy(vertex)
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise ValueError(f"polygon point {i} must be {{'x': number, 'y': number}}") from exc
        # NaN fails this comparison, so it is rejected here too.
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(
                f"polygon point {i} (x={x}, y={y}) is outside 0..1 — station "
                "coordinates are normalized to the frame, so divide pixel "
                "coordinates by the frame width/height first"
            )
        points.append({"x": round(x, 6), "y": round(y, 6)})

    if len(points) < MIN_VERTICES:
        raise ValueError(f"polygon must contain at least {MIN_VERTICES} points")
    if polygon_area(points) < MIN_AREA:
        raise ValueError("polygon has no area — its points are collinear or identical")
    return points


class StationStore:
    """Station ROIs in one JSON file, with an in-process cache.

    Thread-safe: the ingest threads read while the API writes. Reads reload when
    the file's mtime changes, so a new polygon takes effect on the next frame
    without restarting the stream (and an edit by another process is noticed).
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or settings.STATIONS_FILE
        self._lock = threading.RLock()
        self._stations: list[dict] = []
        self._mtime: float = 0.0
        self._loaded = False

    @property
    def path(self) -> str:
        return self._path

    # ── persistence ───────────────────────────────────────────────────────

    def _read_file(self) -> list[dict]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, OSError) as exc:
            # A corrupt file must not take the camera pipeline down; it also must
            # not be silently overwritten on the next write, so log loudly.
            logger.warning("Station file %s unreadable (%s) — treating as empty", self._path, exc)
            return []

        if isinstance(payload, dict):
            stations = payload.get("stations") or []
        else:
            stations = payload or []
        return [s for s in stations if isinstance(s, dict)]

    def _refresh(self) -> None:
        """Reload from disk when the file changed underneath us."""
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            mtime = 0.0
        if not self._loaded or mtime != self._mtime:
            self._stations = self._read_file()
            self._mtime = mtime
            self._loaded = True

    def _write_locked(self) -> None:
        directory = os.path.dirname(os.path.abspath(self._path))
        os.makedirs(directory, exist_ok=True)
        tmp_path = f"{self._path}.tmp"
        payload = {"version": STORE_VERSION, "stations": self._stations}
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        # Atomic swap: a crash mid-write leaves the previous file intact.
        os.replace(tmp_path, self._path)
        try:
            self._mtime = os.path.getmtime(self._path)
        except OSError:
            self._mtime = 0.0

    # ── reads ─────────────────────────────────────────────────────────────

    def list_stations(self, camera_id: str) -> list[dict]:
        """All stations for one camera (copies — callers cannot corrupt state)."""
        wanted = str(camera_id or "")
        with self._lock:
            self._refresh()
            return [dict(s) for s in self._stations if str(s.get("camera_id", "")) == wanted]

    def get_station(self, camera_id: str, station_id: str) -> Optional[dict]:
        wanted = str(station_id or "")
        for station in self.list_stations(camera_id):
            if str(station.get("station_id", "")) == wanted:
                return station
        return None

    def station_for_point(self, camera_id: str, cx: float, cy: float) -> Optional[dict]:
        """The station whose polygon contains ``(cx, cy)``, or ``None``.

        Overlapping polygons resolve to the SMALLEST one — the most specific
        station — with ``station_id`` as a stable tie-break so the reported
        station never flickers between two equally-sized overlaps.
        """
        best: Optional[dict] = None
        best_key: Optional[tuple[float, str]] = None
        for station in self.list_stations(camera_id):
            polygon = station.get("polygon") or []
            try:
                if not point_in_polygon(cx, cy, polygon):
                    continue
                area = polygon_area(polygon)
            except (TypeError, ValueError, KeyError, IndexError):
                # A hand-edited or older file must never break pose processing.
                logger.warning(
                    "Skipping station %s with an unusable polygon", station.get("station_id")
                )
                continue
            key = (area, str(station.get("station_id", "")))
            if best_key is None or key < best_key:
                best, best_key = station, key
        return best

    # ── writes ────────────────────────────────────────────────────────────

    def set_station(
        self,
        camera_id: str,
        station_id: str,
        station_name: str = "",
        polygon=None,
    ) -> dict:
        """Create or replace one station. Returns the stored record."""
        cid = str(camera_id or "").strip()
        sid = str(station_id or "").strip()
        if not cid:
            raise ValueError("camera_id is required")
        if not sid:
            raise ValueError("station_id is required")
        points = normalize_polygon(polygon)

        with self._lock:
            self._refresh()
            existing = next(
                (
                    s
                    for s in self._stations
                    if str(s.get("camera_id", "")) == cid
                    and str(s.get("station_id", "")) == sid
                ),
                None,
            )
            if existing is not None:
                existing["station_name"] = str(station_name or sid)
                existing["polygon"] = points
                existing["updated_at"] = _now_iso()
                record = existing
            else:
                record = {
                    "station_id": sid,
                    "camera_id": cid,
                    "station_name": str(station_name or sid),
                    "polygon": points,
                    "created_at": _now_iso(),
                }
                self._stations.append(record)
            self._write_locked()
            return dict(record)

    def delete_station(self, camera_id: str, station_id: str) -> bool:
        """Remove one station. Returns True when a record was removed."""
        cid = str(camera_id or "")
        sid = str(station_id or "")
        with self._lock:
            self._refresh()
            before = len(self._stations)
            self._stations = [
                s
                for s in self._stations
                if not (
                    str(s.get("camera_id", "")) == cid
                    and str(s.get("station_id", "")) == sid
                )
            ]
            if len(self._stations) == before:
                return False
            self._write_locked()
            return True


_store: Optional[StationStore] = None
_store_lock = threading.Lock()


def get_station_store() -> StationStore:
    """Process-wide station store (lazily created)."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = StationStore()
    return _store
