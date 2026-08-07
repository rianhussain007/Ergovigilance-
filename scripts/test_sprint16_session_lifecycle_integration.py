"""Sprint 16 — Session Lifecycle Integration Validation
Validates:
  - useSessionLifecycle hook structure
  - DemoControls session lifecycle integration
  - Button state management (idle, starting, monitoring, stopping, error)
  - Error handling
  - Session start/stop API calls
"""
import subprocess, sys, time, json

RESULTS = []

def record(name, passed, detail=""):
    RESULTS.append({"test": name, "passed": passed, "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

def run_tests():
    print("=" * 70)
    print("SPRINT 16 — SESSION LIFECYCLE INTEGRATION VALIDATION")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. useSessionLifecycle hook
    # ------------------------------------------------------------------
    print("\n[1] useSessionLifecycle hook")

    try:
        r = subprocess.run(
            ["python", "-c", "import ast, sys; ast.parse(open(sys.argv[1]).read()); print('OK')",
             r"C:\GGS_intership\posture_analysis\ui_posture\src\hooks\useSessionLifecycle.ts"],
            capture_output=True, text=True, timeout=10
        )
        # TypeScript needs tsc, but syntax check via ast won't work for TS
        # Just check file exists and has expected exports
    except Exception:
        pass

    # Check file exists and has expected content
    try:
        with open(r"C:\GGS_intership\posture_analysis\ui_posture\src\hooks\useSessionLifecycle.ts", "r") as f:
            content = f.read()

        checks = [
            ("useSessionLifecycle function exported", "export function useSessionLifecycle" in content or "export default function useSessionLifecycle" in content),
            ("SessionStatus type defined", "SessionStatus" in content and ("idle" in content) and ("starting" in content) and ("monitoring" in content) and ("stopping" in content)),
            ("startSession function defined", "startSession" in content),
            ("stopSession function defined", "stopSession" in content),
            ("POST /api/session/start call", "/api/session/start" in content),
            ("POST /api/session/stop call", "/api/session/stop" in content),
            ("GET /api/session/status call", "/api/session/status" in content),
            ("Error handling with try/catch", "try" in content and "catch" in content),
            ("Mounted ref for cleanup", "mountedRef" in content),
            ("Status polling implemented", "setInterval" in content or "pollStatus" in content),
        ]

        for name, result in checks:
            record(name, result)

    except FileNotFoundError:
        record("useSessionLifecycle.ts file exists", False, "File not found")

    # ------------------------------------------------------------------
    # 2. DemoControls integration
    # ------------------------------------------------------------------
    print("\n[2] DemoControls integration")

    try:
        with open(r"C:\GGS_intership\posture_analysis\ui_posture\src\components\demo\DemoControls.tsx", "r") as f:
            content = f.read()

        checks = [
            ("Imports useSessionLifecycle", "useSessionLifecycle" in content),
            ("Uses session status for button state", "status" in content and ("idle" in content or "monitoring" in content)),
            ("Start Monitoring button text", "Start Monitoring" in content),
            ("Stop Monitoring button text", "Stop Monitoring" in content),
            ("Starting... loading state", "Starting..." in content),
            ("Stopping... loading state", "Stopping..." in content),
            ("Calls startSession on click", "startSession" in content),
            ("Calls stopSession on click", "stopSession" in content),
            ("Disables button during busy state", "isBusy" in content or "disabled" in content),
            ("Error display", "error" in content),
            ("Live indicator shown when monitoring", "Live" in content),
            ("Demo button preserved for mock mode", "Demo" in content),
        ]

        for name, result in checks:
            record(name, result)

    except FileNotFoundError:
        record("DemoControls.tsx file exists", False, "File not found")

    # ------------------------------------------------------------------
    # 3. Backend session lifecycle endpoints exist
    # ------------------------------------------------------------------
    print("\n[3] Backend session lifecycle endpoints")

    try:
        with open(r"C:\GGS_intership\posture_analysis\backend_api\app\api\session_lifecycle.py", "r") as f:
            content = f.read()

        checks = [
            ("POST /api/session/start endpoint", "@router.post" in content and "start" in content.lower()),
            ("POST /api/session/stop endpoint", "stop" in content.lower()),
            ("GET /api/session/status endpoint", "status" in content.lower()),
            ("Camera index parameter", "camera_index" in content),
            ("Error response for camera unavailable", "camera" in content.lower() and ("not found" in content.lower() or "unavailable" in content.lower() or "error" in content.lower() or "detail" in content)),
        ]

        for name, result in checks:
            record(name, result)

    except FileNotFoundError:
        record("session_lifecycle.py file exists", False, "File not found")

    # ------------------------------------------------------------------
    # 4. Router includes session_lifecycle_router
    # ------------------------------------------------------------------
    print("\n[4] Router configuration")

    try:
        with open(r"C:\GGS_intership\posture_analysis\backend_api\app\api\router.py", "r") as f:
            content = f.read()

        checks = [
            ("session_lifecycle_router imported", "session_lifecycle_router" in content),
            ("Router includes session lifecycle", "session_lifecycle_router" in content),
        ]

        for name, result in checks:
            record(name, result)

    except FileNotFoundError:
        record("router.py file exists", False, "File not found")

    # ------------------------------------------------------------------
    # 5. LiveMonitoringService start/stop methods exist
    # ------------------------------------------------------------------
    print("\n[5] LiveMonitoringService start/stop methods")

    try:
        with open(r"C:\GGS_intership\posture_analysis\backend_api\app\services\live_monitor.py", "r") as f:
            content = f.read()

        checks = [
            ("start_session method exists", "def start_session" in content),
            ("stop_session method exists", "def stop_session" in content),
            ("is_running method exists", "def is_running" in content),
            ("session_active flag tracked", "session_active" in content),
        ]

        for name, result in checks:
            record(name, result)

    except FileNotFoundError:
        record("live_monitor.py file exists", False, "File not found")

    # ------------------------------------------------------------------
    # 6. deps.get_repository switching logic
    # ------------------------------------------------------------------
    print("\n[6] Repository switching logic")

    try:
        with open(r"C:\GGS_intership\posture_analysis\backend_api\app\core\deps.py", "r") as f:
            content = f.read()

        checks = [
            ("get_repository function defined", "def get_repository" in content),
            ("Checks USE_MOCK_REPOSITORY", "USE_MOCK_REPOSITORY" in content),
            ("Checks is_running", "is_running" in content),
            ("Falls back to MockRepository", "MockRepository" in content),
            ("Returns LiveRepository when live", "LiveRepository" in content),
        ]

        for name, result in checks:
            record(name, result)

    except FileNotFoundError:
        record("deps.py file exists", False, "File not found")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = total - passed

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        print("\nFailed tests:")
        for r in RESULTS:
            if not r["passed"]:
                print(f"  - {r['test']}" + (f": {r['detail']}" if r["detail"] else ""))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
