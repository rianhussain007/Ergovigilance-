"""Start vite dev server and keep it alive."""
import subprocess, os, time

os.chdir("C:/GGS_intership/posture_analysis/ui_posture")
proc = subprocess.Popen(
    ["npx.cmd", "vite", "--host", "0.0.0.0", "--port", "5173"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
with open("vite.pid", "w") as f:
    f.write(str(proc.pid))
print(f"Vite started (PID {proc.pid})")

# Wait for it to be ready
for _ in range(30):
    time.sleep(1)
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:5173/", timeout=2)
        print("Frontend ready")
        break
    except Exception:
        pass
else:
    print("Frontend failed to start")
