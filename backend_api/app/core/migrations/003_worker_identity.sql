-- Worker identity controls (consent-safe identification).
-- identity_mode : 'face' (camera face recognition) | 'badge' (badge/QR scan only) | 'off'
-- consent_status: 'granted' | 'pending' | 'denied'
--   A worker whose consent is 'denied' (or whose identity_mode is 'badge'/'off')
--   is never matched by face recognition at runtime.
-- badge_id     : optional opaque badge/QR identifier used for badge-based check-in.
ALTER TABLE workers ADD COLUMN identity_mode TEXT NOT NULL DEFAULT 'face';
ALTER TABLE workers ADD COLUMN consent_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE workers ADD COLUMN badge_id TEXT;
