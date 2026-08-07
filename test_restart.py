import httpx
r = httpx.post("http://localhost:8440/api/auth/login", json={"email":"admin@example.local","password":"AdminPass123!"})
token = r.json()["token"]
r2 = httpx.get("http://localhost:8440/api/reports/session/SESH-20260630_111201/pdf", headers={"Authorization":f"Bearer {token}"})
print(f"Status: {r2.status_code}  Size: {len(r2.content)} bytes  Type: {r2.headers['content-type']}")
print("First bytes:", r2.content[:8])
