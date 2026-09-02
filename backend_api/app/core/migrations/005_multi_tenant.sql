-- Migration 005 — Multi-tenant organization support.
-- Adds organizations table and org_id to all data tables for tenant isolation.
-- Each factory/company is a separate organization with its own users, workers,
-- sessions, alerts, and audit trail.

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL DEFAULT 'pilot' CHECK(plan IN ('pilot', 'starter', 'professional', 'enterprise')),
    industry TEXT DEFAULT '',
    country TEXT DEFAULT '',
    timezone TEXT DEFAULT 'UTC',
    max_cameras INTEGER DEFAULT 3,
    max_workers INTEGER DEFAULT 50,
    api_key TEXT UNIQUE,
    settings TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_org_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_org_api_key ON organizations(api_key);

-- Add org_id to users
ALTER TABLE users ADD COLUMN org_id INTEGER REFERENCES organizations(id);

-- Add org_id to workers
ALTER TABLE workers ADD COLUMN org_id INTEGER REFERENCES organizations(id);

-- Add org_id to alerts
ALTER TABLE alerts ADD COLUMN org_id INTEGER REFERENCES organizations(id);

-- Add org_id to audit_log
ALTER TABLE audit_log ADD COLUMN org_id INTEGER REFERENCES organizations(id);

-- Add org_id to pilot_requests (optional, for tracking which org requested)
ALTER TABLE pilot_requests ADD COLUMN org_id INTEGER REFERENCES organizations(id);

-- Add org_id to user_settings
ALTER TABLE user_settings ADD COLUMN org_id INTEGER REFERENCES organizations(id);

-- Organization-scoped API keys for cloud core access
CREATE TABLE IF NOT EXISTS org_api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    scopes TEXT DEFAULT 'read,write',
    last_used_at TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_api_keys_org ON org_api_keys(org_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON org_api_keys(key_hash);

-- Organization invitations
CREATE TABLE IF NOT EXISTS org_invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator',
    invited_by INTEGER REFERENCES users(id),
    accepted_at TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invitations_org ON org_invitations(org_id);
CREATE INDEX IF NOT EXISTS idx_invitations_email ON org_invitations(email);

-- Insert default demo organization
INSERT OR IGNORE INTO organizations (name, slug, plan, industry, country, max_cameras, max_workers, api_key, created_at, updated_at)
VALUES (
    'Demo Factory',
    'demo-factory',
    'enterprise',
    'Manufacturing',
    'IN',
    50,
    500,
    'ergo_demo_key_' || hex(randomblob(16)),
    datetime('now'),
    datetime('now')
);

-- Insert second demo organization for multi-tenant testing
INSERT OR IGNORE INTO organizations (name, slug, plan, industry, country, max_cameras, max_workers, api_key, created_at, updated_at)
VALUES (
    'Acme Manufacturing',
    'acme-mfg',
    'professional',
    'Automotive',
    'US',
    10,
    100,
    'ergo_acme_key_' || hex(randomblob(16)),
    datetime('now'),
    datetime('now')
);

-- Migrate existing users to demo-factory org
UPDATE users SET org_id = (SELECT id FROM organizations WHERE slug = 'demo-factory')
WHERE org_id IS NULL;

-- Migrate existing workers to demo-factory org
UPDATE workers SET org_id = (SELECT id FROM organizations WHERE slug = 'demo-factory')
WHERE org_id IS NULL;

-- Migrate existing alerts to demo-factory org
UPDATE alerts SET org_id = (SELECT id FROM organizations WHERE slug = 'demo-factory')
WHERE org_id IS NULL;

-- Migrate existing audit_log to demo-factory org
UPDATE audit_log SET org_id = (SELECT id FROM organizations WHERE slug = 'demo-factory')
WHERE org_id IS NULL;
