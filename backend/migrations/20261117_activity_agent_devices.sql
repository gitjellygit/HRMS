-- Explicit activity-agent pilot schema for existing databases; no existing employee data changes.
CREATE TABLE IF NOT EXISTS activity_agent_devices (
 id SERIAL PRIMARY KEY,
 employee_id INTEGER NOT NULL REFERENCES employees(id),
 token_hash VARCHAR(64) NOT NULL UNIQUE,
 device_label VARCHAR(120) NOT NULL DEFAULT 'Windows workstation',
 state VARCHAR(20) NOT NULL DEFAULT 'not_started',
 last_seen TIMESTAMPTZ,
 stopped_at TIMESTAMPTZ,
 exit_reason TEXT NOT NULL DEFAULT '',
 active_seconds INTEGER NOT NULL DEFAULT 0,
 idle_seconds INTEGER NOT NULL DEFAULT 0,
 revoked BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_activity_agent_devices_employee_id ON activity_agent_devices(employee_id);
