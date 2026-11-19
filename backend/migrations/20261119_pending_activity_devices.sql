-- Pending, company-authorized devices can register before an employee record exists.
-- Activity heartbeats stay forbidden until HR assigns an active employee.
ALTER TABLE activity_agent_devices ALTER COLUMN employee_id DROP NOT NULL;
CREATE TABLE IF NOT EXISTS activity_agent_invitations (
 id SERIAL PRIMARY KEY,
 code_hash VARCHAR(64) NOT NULL UNIQUE,
 created_by INTEGER NOT NULL REFERENCES employees(id),
 expires_at TIMESTAMPTZ NOT NULL,
 used_at TIMESTAMPTZ,
 device_id INTEGER REFERENCES activity_agent_devices(id)
);
CREATE INDEX IF NOT EXISTS ix_activity_agent_invitations_expires ON activity_agent_invitations(expires_at);
