-- Run once against an existing PostgreSQL database before deploying this version.
-- Fresh installations receive the same structure from SQLAlchemy metadata.

ALTER TABLE items ADD COLUMN IF NOT EXISTS color VARCHAR(80);
ALTER TABLE items ADD COLUMN IF NOT EXISTS measurements TEXT;

-- Existing records must be completed deliberately instead of silently publishing
-- incomplete product cards.
UPDATE items
SET color = COALESCE(NULLIF(color, ''), 'Не указан'),
    measurements = COALESCE(NULLIF(measurements, ''), 'Не указаны')
WHERE color IS NULL OR measurements IS NULL;

ALTER TABLE items ALTER COLUMN color SET NOT NULL;
ALTER TABLE items ALTER COLUMN measurements SET NOT NULL;
ALTER TABLE items ALTER COLUMN material SET NOT NULL;
ALTER TABLE items ALTER COLUMN size SET NOT NULL;
ALTER TABLE items ALTER COLUMN style SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_items_catalog_specs
    ON items (publication_status, availability, category, condition, color);
CREATE INDEX IF NOT EXISTS ix_items_search_specs
    ON items (category, style, material, color, size);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES deal_requests(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL CHECK (length(trim(body)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_messages_request_id ON messages (request_id);
