from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2


@dataclass
class CameraInfo:
    index: int
    backend_id: int
    backend_name: str
    width: int
    height: int
    fps: float
    name: str = ""
    max_width: int = 0
    max_height: int = 0


BACKENDS = [
    (cv2.CAP_DSHOW, "DSHOW"),
    (cv2.CAP_MSMF, "MSMF"),
    (cv2.CAP_ANY, "ANY"),
]

_DEFAULT_MAX_INDEX = 10


def _get_camera_names() -> dict[int, str]:
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq 'Camera' } "
            "| Select-Object Name | ConvertTo-Json"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            return {i: item["Name"] for i, item in enumerate(data)}
    except Exception:
        pass
    return {}


def _try_open(index: int, backend_id: int) -> Optional[cv2.VideoCapture]:
    try:
        cap = cv2.VideoCapture(index, backend_id)
        if cap.isOpened():
            return cap
        cap.release()
    except Exception:
        pass
    return None


def _get_max_resolution(cap: cv2.VideoCapture) -> tuple[int, int]:
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_res = (orig_w, orig_h)
    test_res = [(1280, 720), (1920, 1080), (2560, 1440)]
    for tw, th in test_res:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, tw)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, th)
        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if aw * ah > max_res[0] * max_res[1]:
            max_res = (aw, ah)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, orig_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, orig_h)
    return max_res


def _info_from_cap(cap: cv2.VideoCapture, index: int, backend_id: int) -> CameraInfo:
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    actual = cap.getBackendName()
    mw, mh = _get_max_resolution(cap)
    return CameraInfo(index, backend_id, actual, w, h, fps, max_width=mw, max_height=mh)


def _match_names(cameras: List[CameraInfo], wmi_names: dict[int, str]) -> None:
    if not cameras or not wmi_names:
        return

    # Sort cameras by max resolution descending (higher res = external/USB camera)
    sorted_cams = sorted(cameras, key=lambda c: -c.max_width * c.max_height)
    # Sort WMI names: prioritize names with HD/Webcam/USB/2MP keywords
    sorted_wmi = sorted(wmi_names.items(), key=lambda x: (
        0 if any(kw in x[1].lower() for kw in ['hd', 'webcam', 'usb', '2mp', '1080p', 'external'])
        else 1
    ))

    for cam, (_, name) in zip(sorted_cams, sorted_wmi):
        cam.name = name

    # Assign remaining names to remaining cameras
    named_indices = {c.index for c in cameras if c.name}
    for cam in cameras:
        if not cam.name:
            remaining = [n for i, n in wmi_names.items() if i not in named_indices]
            cam.name = remaining[0] if remaining else f"Camera {cam.index}"
            named_indices.add(cam.index)


def detect_cameras(fast: bool = True, max_index: int = 5) -> List[CameraInfo]:
    wmi_names = _get_camera_names()
    backends_to_try = BACKENDS[:1] if fast else BACKENDS
    cameras: List[CameraInfo] = []
    for idx in range(max_index + 1):
        for backend_id, _ in backends_to_try:
            cap = _try_open(idx, backend_id)
            if cap is not None:
                info = _info_from_cap(cap, idx, backend_id)
                cap.release()
                cameras.append(info)
                break
    _match_names(cameras, wmi_names)
    return cameras


def get_best_camera() -> Optional[CameraInfo]:
    for idx in range(6):
        cap = _try_open(idx, cv2.CAP_DSHOW)
        if cap is not None:
            info = _info_from_cap(cap, idx, cv2.CAP_DSHOW)
            cap.release()
            return info
    for idx in range(6):
        cap = _try_open(idx, cv2.CAP_MSMF)
        if cap is not None:
            info = _info_from_cap(cap, idx, cv2.CAP_MSMF)
            cap.release()
            return info
    for idx in range(6):
        cap = _try_open(idx, cv2.CAP_ANY)
        if cap is not None:
            info = _info_from_cap(cap, idx, cv2.CAP_ANY)
            cap.release()
            return info
    return None


def _name_camera(info: CameraInfo, cameras: List[CameraInfo]) -> None:
    for c in cameras:
        if c.index == info.index:
            info.name = c.name
            return
    wmi_names = _get_camera_names()
    info.name = wmi_names.get(info.index, f"Camera {info.index}")


def open_camera(index: Optional[int] = None) -> Tuple[cv2.VideoCapture, CameraInfo]:
    if index is not None:
        for backend_id, _ in BACKENDS:
            cap = _try_open(index, backend_id)
            if cap is not None:
                info = _info_from_cap(cap, index, backend_id)
                return cap, info
        raise RuntimeError(f"Cannot open camera at index {index} with any backend.")
    best = get_best_camera()
    if best is None:
        raise RuntimeError("No camera found.")
    cap = _try_open(best.index, best.backend_id)
    if cap is None:
        raise RuntimeError(f"Failed to open camera at index {best.index}")
    return cap, best


def get_camera_from_args() -> Tuple[cv2.VideoCapture, CameraInfo]:
    parser = argparse.ArgumentParser(
        description="Posture Analysis - Camera Selection"
    )
    parser.add_argument("--camera", type=int, default=None,
                        help="Camera index to use (e.g. 0, 1). Auto-selects best if omitted.")
    args, _ = parser.parse_known_args()

    cameras = detect_cameras(fast=True)

    print()
    print("Detected Cameras:")
    for c in cameras:
        print(f"  [{c.index}] {c.name}")
    for idx in range(_DEFAULT_MAX_INDEX + 1):
        if not any(c.index == idx for c in cameras):
            wmi_names = _get_camera_names()
            if idx in wmi_names:
                print(f"  [{idx}] {wmi_names[idx]} (unavailable)")

    if args.camera is not None:
        cap, info = open_camera(args.camera)
        _name_camera(info, cameras)
    else:
        if not cameras:
            cameras = detect_cameras(fast=False)
        if not cameras:
            raise RuntimeError("No camera found.")
        cameras.sort(key=lambda c: (-c.max_width * c.max_height, -c.index))
        cap, info = open_camera(cameras[0].index)
        _name_camera(info, cameras)

    print(f"\nUsing Camera: {info.index} ({info.name})")
    print(f"  Backend: {info.backend_name} | Resolution: {info.width}x{info.height} | FPS: {info.fps:.0f}")
    return cap, info
