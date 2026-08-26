-- Multi-sample face enrollment: up to N embedding samples per worker so
-- recognition stays accurate across angles, distance and lighting instead of
-- depending on one ideal photo. Existing single embeddings are migrated as
-- sample 0 so no worker loses their enrollment.
CREATE TABLE IF NOT EXISTS worker_face_samples (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id    TEXT NOT NULL,
    embedding    TEXT NOT NULL,
    enrolled_at  TEXT NOT NULL,
    sample_index INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_face_samples_worker ON worker_face_samples(worker_id);
INSERT INTO worker_face_samples (worker_id, embedding, enrolled_at, sample_index)
SELECT worker_id, embedding, updated_at, 0 FROM worker_faces;
DROP TABLE worker_faces;
