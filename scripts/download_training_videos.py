"""Download diverse ergonomic training videos for model improvement."""

import subprocess
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent / "data" / "datasets" / "diverse_training" / "youtube"

# Videos to download organized by category
VIDEOS = {
    "lifting_heavy": [
        "https://www.youtube.com/watch?v=z4epeIusue0",  # How To Lift Heavy Weight Safely
        "https://www.youtube.com/watch?v=8DJi4PrdFCg",  # Walking worker (already have)
        "https://www.youtube.com/watch?v=N4OQFi4UrR4",  # Walking worker (already have)
    ],
    "inspection": [
        "https://www.youtube.com/watch?v=sV4Lm5GF3dI",  # Quality inspection factory
        "https://www.youtube.com/watch?v=9s-oFRJJhh8",   # Assembly worker
        "https://www.youtube.com/watch?v=E943iVhG9dc",   # Assembly worker
    ],
    "seated_work": [
        "https://www.youtube.com/watch?v=TYrS7pxscgc",  # Walking worker
    ],
    "walking_reaching": [
        "https://www.youtube.com/watch?v=8DJi4PrdFCg",  # Walking worker
        "https://www.youtube.com/watch?v=N4OQFi4UrR4",  # Walking worker
    ],
}

def download_video(url: str, output_dir: Path, max_duration: int = 120) -> bool:
    """Download a single video, limiting duration."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "yt-dlp",
        "--format", "mp4",
        "--max-filesize", "50M",
        "--match-filter", f"duration<={max_duration}",
        "--output", str(output_dir / "%(id)s.%(ext)s"),
        "--no-playlist",
        url,
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"  [OK] Downloaded: {url}")
            return True
        else:
            print(f"  [FAIL] Failed: {url} - {result.stderr[:100]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Timeout: {url}")
        return False
    except Exception as e:
        print(f"  [ERROR] Error: {url} - {e}")
        return False

def main():
    print("=== Downloading Ergonomic Training Videos ===\n")
    
    total = 0
    success = 0
    
    for category, urls in VIDEOS.items():
        print(f"\n--- {category.upper()} ---")
        output_dir = BASE_DIR / category
        
        for url in urls:
            total += 1
            # Skip if already downloaded
            video_id = url.split("v=")[-1]
            if list(output_dir.glob(f"{video_id}.*")):
                print(f"  [SKIP] Already exists: {video_id}")
                success += 1
                continue
            
            if download_video(url, output_dir):
                success += 1
    
    print(f"\n=== Done: {success}/{total} videos downloaded ===")
    
    # Count total videos
    total_videos = 0
    for subdir in BASE_DIR.iterdir():
        if subdir.is_dir():
            count = len(list(subdir.glob("*.mp4")))
            total_videos += count
            print(f"  {subdir.name}: {count} videos")
    
    print(f"\nTotal training videos: {total_videos}")

if __name__ == "__main__":
    main()
