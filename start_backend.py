"""Start uvicorn backend and keep it running in background."""
import subprocess, sys, time, os

os.chdir("C:/GGS_intership/posture_analysis/backend_api")
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Write PID so it can be killed later
with open("backend.pid", "w") as f:
    f.write(str(proc.pid))

print(f"Backend started (PID {proc.pid})")
