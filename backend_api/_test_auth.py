"""Test the camera API cache with valid auth."""
import requests, time, json

# Login
r = requests.post('http://localhost:8000/api/auth/login',
                  json={'email': 'safety@example.local', 'password': 'SafetyPass123!'})
print('Login status:', r.status_code)
data = r.json()
print('Response keys:', list(data.keys()))
token = data.get('access_token', data.get('token', ''))
print('Token length:', len(token))

if not token:
    print('No token, cannot proceed')
    exit(1)

headers = {'Authorization': f'Bearer {token}'}

# Call /api/cameras 3 times
for i in range(3):
    r = requests.get('http://localhost:8000/api/cameras', headers=headers)
    cams = r.json()
    print(f'\nCall {i+1}: status={r.status_code}, cameras={len(cams)}')
    for c in cams:
        print(f'  [{c["id"]}] {c["name"]} — {c["status"]}')
    if i < 2:
        time.sleep(2)

print('\nDone. Check server log for "[get_cameras]" probe messages.')
