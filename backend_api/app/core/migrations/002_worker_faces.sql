-- Worker face enrollment: one row per worker with an enrolled face photo.
-- embedding stores the normalized 128-dim SFace embedding as a JSON array
-- (readable, and small enough at ~2 KB per worker).
CREATE TABLE IF NOT EXISTS worker_faces (
    worker_id    TEXT PRIMARY KEY,
    embedding    TEXT NOT NULL,
    enrolled_at  TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
