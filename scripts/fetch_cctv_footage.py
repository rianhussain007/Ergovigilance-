#!/usr/bin/env python3
"""Fetch + normalize trial footage for the TRL-6 relevant-environment demo.

Sources (license-checked; see docs/FOOTAGE_PROVENANCE.csv emitted alongside):

1. UCSD Anomaly Detection Dataset — raw static-camera CCTV crowd clips
   (TIFF frame sequences assembled to mp4). Source: svcl.ucsd.edu, research
   use with citation. Published MD5 verifies the archive.
2. PETS2009 View001 demo clips (.mov, H.264) — hosted by UCSD SVCL; PETS
   license permits free download for academic AND industrial research with
   attribution. These carry the original crowd-counting overlay drawings.
3. Local worker videos already under data/datasets/diverse_training/ —
   copied + normalized (no network; provenance recorded as local reuse).

Idempotent: existing normalized outputs are kept (skip), --force re-does them.
Footage stays under data/datasets/ (gitignored); only this script and the
manifest CSV are committed. Usage: python scripts/fetch_cctv_footage.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "datasets" / "cctv_trial"
WORK = OUT / "_work"
MANIFEST = ROOT / "docs" / "FOOTAGE_PROVENANCE.csv"

UCSD_URL = "http://www.svcl.ucsd.edu/projects/anomaly/UCSD_Anomaly_Dataset.tar.gz"
UCSD_MD5 = "5006421b89885f45a6f93b041145f2eb"
UCSD_ARCHIVE = OUT / "UCSD_Anomaly_Dataset.tar.gz"

PETS_BASE = "http://www.svcl.ucsd.edu/projects/peoplecnt/petsvideo/"
# The count_* demos are split-screen (camera panel | bird's-eye schematic) —
# crop to the camera panel so the pipeline sees only CCTV frames.
PETS_SPLIT = {"count_13-57-View_001.mov", "count_14-06-View_001.mov",
              "count_14-17-View_001.mov"}
PETS_CROP = "crop=386:384:0:0"
PETS_CLIPS = [
    ("count_13-57-View_001.mov", "pets_s1l1_13-57.mp4", "S1.L1 medium crowd, View001"),
    ("count_14-06-View_001.mov", "pets_s1l2_14-06.mp4", "S1.L2 high crowd, View001"),
    ("count_14-17-View_001.mov", "pets_s1l3_14-17.mp4", "S1.L3 dense crowd, View001"),
    ("events_14-16-View_001.mov", "pets_s3mf_14-16.mp4", "S3 running dense crowd, View001"),
]

# UCSD clips: (archive-internal folder, output name, description)
UCSD_CLIPS = [
    ("UCSD_Anomaly_Dataset.v1p2/UCSDped1/Test/Test001", "ucsd_peds1_test001.mp4",
     "Peds1 test clip, crowd walking toward camera"),
    ("UCSD_Anomaly_Dataset.v1p2/UCSDped1/Test/Test007", "ucsd_peds1_test007.mp4",
     "Peds1 test clip, elevated static CCTV walkway"),
    ("UCSD_Anomaly_Dataset.v1p2/UCSDped2/Test/Test001", "ucsd_peds2_test001.mp4",
     "Peds2 test clip, movement parallel to camera plane"),
]

# Local worker footage (multi-person capable) already in the repo tree.
LOCAL_CLIPS = [
    (ROOT / "data" / "datasets" / "diverse_training" / "youtube" /
     "Ergonomic Risks in Automotive Assembly Lines.mp4",
     "local_assembly_lines.mp4", "assembly line, multiple workers (local reuse)"),
    (ROOT / "data" / "datasets" / "diverse_training" / "youtube" /
     "Work Safely： Lifting in the warehouse.mp4",
     "local_warehouse_lifting.mp4", "warehouse lifting, team setting (local reuse)"),
    (ROOT / "data" / "datasets" / "diverse_training" / "youtube" /
     "Manual Handling Training Video - Unitas3d.mp4",
     "local_manual_handling.mp4", "manual handling team demo (local reuse)"),
]

MAX_W = 1280
MANIFEST_FIELDS = [
    "filename", "local_md5", "source_name", "source_url", "license",
    "retrieved_utc", "method", "description", "notes",
]


def log(msg: str) -> None:
    # Console may be cp1252; keep Unicode filenames printable (e.g. U+FF1A).
    print(f"[fetch] {msg}".encode("cp1252", "replace").decode("cp1252"), flush=True)


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"cmd failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr[-2000:]}")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def normalize(src: Path, dst: Path) -> None:
    """Transcode to H.264 mp4, max width MAX_W, even dimensions."""
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"scale='min({MAX_W},iw)':-2:force_original_aspect_ratio=decrease,"
               "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-an", str(dst),
    ])


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        log(f"have {dest.name} ({dest.stat().st_size // (1 << 20)} MB)")
        return
    log(f"GET {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "ergovigilance-trl6/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    tmp.replace(dest)
    log(f"  -> {dest.name} ({dest.stat().st_size // (1 << 20)} MB)")


def extract_ucsd_clips(archive: Path, specs: list[tuple[str, str, str]]) -> dict[str, Path]:
    """Single pass over the tar: pull every requested TIFF folder, assemble mp4s.

    A gzip stream cannot be re-seeked cheaply, so all clips are harvested in
    one iteration instead of one full decompression per clip.
    Returns {out_name: mp4 path} for clips that succeeded.
    """
    wanted = {inner: out_name for inner, out_name, _ in specs}
    desc_by_out = {out_name: desc for inner, out_name, desc in specs}
    # Skip clips already built.
    pending = {inner: out for inner, out in wanted.items() if not (OUT / out).exists()}
    for out in wanted.values():
        if (OUT / out).exists():
            log(f"have {out}")
    if not pending:
        return {out: OUT / out for out in wanted.values()}

    staged: dict[str, list[Path]] = {inner: [] for inner in pending}
    # Unique staging dir per clip: UCSDped1/Test/Test001 and UCSDped2/Test/Test001
    # share Path(...).name and would silently interleave files.
    stage_dir = {inner: WORK / wanted[inner].removesuffix(".mp4") for inner in pending}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if not member.isfile() or not member.name.lower().endswith((".tif", ".tiff")):
                continue
            match = next((inner for inner in pending if member.name.startswith(inner + "/")),
                         None)
            if match is None:
                continue
            frames_dir = stage_dir[match]
            frames_dir.mkdir(parents=True, exist_ok=True)
            target = frames_dir / Path(member.name).name
            with tar.extractfile(member) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            staged[match].append(target)
            if all(len(v) >= 400 for v in staged.values()):
                break

    built: dict[str, Path] = {out: OUT / out for out in wanted.values()
                              if (OUT / out).exists()}
    for inner, out_name in pending.items():
        tifs = sorted(staged.get(inner, []))
        if not tifs:
            log(f"WARN: no TIFFs found under {inner}")
            continue
        frames_dir = tifs[0].parent
        name = tifs[0].name
        digits = len(name.rsplit("_", 1)[-1].split(".")[0])
        prefix, sep, rest = name.rpartition("_")
        if not sep:  # plain "001.tif" style — no prefix segment
            prefix, rest = "", name
        stem, ext = rest.rsplit(".", 1)
        start = int(stem)
        pattern = f"{prefix}{sep}%0{digits}d.{ext}"
        dst = OUT / out_name
        log(f"assembling {len(tifs)} TIFFs ({pattern}, start={start}) -> {out_name}")
        run([
            "ffmpeg", "-y", "-framerate", "10",
            "-start_number", str(start),
            "-i", str(frames_dir / pattern),
            "-vf", f"scale='min({MAX_W},iw)':-2:force_original_aspect_ratio=decrease,"
                   "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            str(dst),
        ])
        for f in frames_dir.iterdir():
            f.unlink()
        frames_dir.rmdir()
        built[out_name] = dst
    return built


def write_manifest(rows: list[dict]) -> None:
    """Upsert into the existing manifest so --skip-* runs don't drop rows."""
    merged: dict[str, dict] = {}
    if MANIFEST.exists():
        with MANIFEST.open("r", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                merged[row["filename"]] = row
    merged.update({r["filename"]: r for r in rows})
    # Manifest describes files on disk only.
    merged = {name: row for name, row in merged.items() if (OUT / name).exists()}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in merged.values():
            writer.writerow(row)
    log(f"manifest -> {MANIFEST.relative_to(ROOT)} ({len(merged)} rows)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-ucsd", action="store_true", help="skip the 707MB archive")
    ap.add_argument("--skip-pets", action="store_true")
    ap.add_argument("--skip-local", action="store_true")
    ap.add_argument("--force", action="store_true", help="rebuild existing outputs")
    args = ap.parse_args()

    if not ffmpeg_available():
        log("ERROR: ffmpeg not on PATH")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.force:
        for f in OUT.glob("*.mp4"):
            f.unlink()

    # -- 1. UCSD -------------------------------------------------------------
    if not args.skip_ucsd:
        if UCSD_ARCHIVE.exists() and UCSD_ARCHIVE.stat().st_size < 600 * (1 << 20):
            log(f"WARN: partial UCSD archive ({UCSD_ARCHIVE.stat().st_size} bytes) — "
                "run curl -C - to resume, skipping extract this pass")
        elif UCSD_ARCHIVE.exists():
            digest = md5(UCSD_ARCHIVE)
            if digest != UCSD_MD5:
                log(f"WARN: UCSD md5 mismatch ({digest} != {UCSD_MD5}) — skipping extract")
            else:
                log("UCSD archive md5 OK")
                built = extract_ucsd_clips(UCSD_ARCHIVE, UCSD_CLIPS)
                for inner, out_name, desc in UCSD_CLIPS:
                    dst = built.get(out_name)
                    if dst:
                        rows.append({
                            "filename": out_name, "local_md5": md5(dst),
                            "source_name": "UCSD Anomaly Detection Dataset",
                            "source_url": UCSD_URL, "license":
                            "research use with citation (svcl.ucsd.edu)",
                            "retrieved_utc": now,
                            "method": "tar.gz download + TIFF->h264 assemble",
                            "description": desc,
                            "notes": "static elevated CCTV, crowds, natural occlusion",
                        })
        else:
            log("UCSD archive absent — download it first (see module docstring)")

    # -- 2. PETS -------------------------------------------------------------
    if not args.skip_pets:
        for src_name, out_name, desc in PETS_CLIPS:
            dst = OUT / out_name
            if dst.exists() and not args.force:
                log(f"have {out_name}")
            else:
                raw = WORK / src_name
                WORK.mkdir(parents=True, exist_ok=True)
                try:
                    download(PETS_BASE + src_name, raw)
                    if src_name in PETS_SPLIT:
                        # Crop forces a re-encode; clips are tiny (~10-20s).
                        run(["ffmpeg", "-y", "-i", str(raw), "-vf", PETS_CROP,
                             "-c:v", "libx264", "-preset", "veryfast",
                             "-pix_fmt", "yuv420p", "-an", str(dst)])
                    else:
                        # Already H.264 in a .mov — remux when possible.
                        try:
                            run(["ffmpeg", "-y", "-i", str(raw), "-c", "copy", str(dst)])
                        except RuntimeError:
                            normalize(raw, dst)
                except Exception as exc:  # source down -> record, continue
                    log(f"WARN: PETS {src_name} failed: {exc}")
                    continue
            if dst.exists():
                rows.append({
                    "filename": out_name, "local_md5": md5(dst),
                    "source_name": "PETS2009 via UCSD SVCL demo",
                    "source_url": PETS_BASE + src_name,
                    "license": "PETS: free download for academic and industrial "
                               "research with attribution (Ferryman & Shahrokni 2009)",
                    "retrieved_utc": now,
                    "method": "direct .mov download + remux",
                    "description": desc,
                    "notes": "carries original crowd-counting overlay drawings",
                })

    # -- 3. local worker footage --------------------------------------------
    if not args.skip_local:
        for src, out_name, desc in LOCAL_CLIPS:
            dst = OUT / out_name
            if dst.exists() and not args.force:
                log(f"have {out_name}")
            elif src.exists():
                log(f"normalizing local {src.name}")
                normalize(src, dst)
            else:
                log(f"WARN: local source missing: {src}")
                continue
            if dst.exists():
                rows.append({
                    "filename": out_name, "local_md5": md5(dst),
                    "source_name": "local diverse_training/youtube",
                    "source_url": "(local reuse, no new download)",
                    "license": "third-party video already in repo for internal "
                               "testing; not redistributed",
                    "retrieved_utc": now,
                    "method": "local transcode (maxw 1280 h264)",
                    "description": desc,
                    "notes": "internal test use only",
                })

    # -- manifest (merge: keep rows for files still present) -----------------
    existing_files = {p.name for p in OUT.glob("*.mp4")}
    rows = [r for r in rows if r["filename"] in existing_files]
    if rows:
        write_manifest(rows)
    counts = {r["source_name"].split()[0] for r in rows}
    log(f"done: {len(rows)} clips in {OUT.relative_to(ROOT)} (sources: {sorted(counts)})")
    if not rows:
        log("ERROR: no clips produced")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
