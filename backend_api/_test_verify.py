"""Verify all three fixes with a fresh session."""
import urllib.request, json, ssl, time

ctx = ssl._create_unverified_context()
API = 'http://localhost:8000'

def get(path, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'{API}{path}', headers=headers, method='GET')
    resp = urllib.request.urlopen(req, context=ctx, timeout=30)
    return json.loads(resp.read())

def post(path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = json.dumps(data).encode() if data else b'{}'
    req = urllib.request.Request(f'{API}{path}', data=body, headers=headers, method='POST')
    resp = urllib.request.urlopen(req, context=ctx, timeout=30)
    return json.loads(resp.read())

login = post('/api/auth/login', {'email': 'admin@example.local', 'password': 'AdminPass123!'})
token = login['token']
print(f'LOGIN: {login["user"]["role"]}')

# Check alerts BEFORE session
alerts = get('/api/alerts', token=token)
active_count = len(alerts.get('active', []))
print(f'\nFix 3 — BEFORE session: {active_count} active alerts (should be 0)')

# Fresh session
h = get('/health')
if h.get('live_session'):
    post('/api/session/stop', token=token)
    time.sleep(2)

post('/api/session/start', {'worker_id': 'worker-001', 'camera_index': 0}, token=token)
time.sleep(5)

# Check 10 frames for safety_state
print(f'\nFix 1 — Tracking safety_state over 10 frames:')
first_states = {}
for i in range(10):
    snap = get('/api/context/snapshot', token=token)
    ss = snap.get('safety_state', '?')
    rl = snap.get('risk_level', '?')
    fr = snap.get('final_risk', 0)
    fn = snap.get('frame_number', 0)
    first_states[ss] = first_states.get(ss, 0) + 1
    print(f'  frame {fn:>5}: safety={ss:>8} risk={rl:>6} final={fr:.1f}')
    time.sleep(0.3)

print(f'  State distribution: {first_states}')

# Check dashboard
dash = get('/api/dashboard', token=token)
live = dash.get('liveStatus', {})
ses = dash.get('session', {})
print(f'\nFix 2 — Dashboard: riskLevel={live.get("riskLevel")} workerStatus={live.get("workerStatus")} cameraStatus={ses.get("cameraStatus")}')

# Check alerts
alerts2 = get('/api/alerts', token=token)
active2 = len(alerts2.get('active', []))
print(f'\nFix 3 — AFTER session: {active2} active alerts')

print(f'\n=== VERIFICATION COMPLETE ===')
