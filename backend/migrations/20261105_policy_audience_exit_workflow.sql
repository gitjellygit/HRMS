-- Employee-pilot HR workflows: review on staging before a production deployment.
-- Back up database first. No existing policy or exit case rows are deleted.
BEGIN;
ALTER TABLE company_policy_records
    ADD COLUMN IF NOT EXISTS audience_ids TEXT NOT NULL DEFAULT '[]';

CREATE TABLE IF NOT EXISTS company_policy_attachments (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES company_policy_records(id),
    filename VARCHAR(180) NOT NULL,
    storage_key VARCHAR(110) NOT NULL,
    uploaded_by INTEGER NOT NULL REFERENCES employees(id)
);
CREATE INDEX IF NOT EXISTS ix_company_policy_attachments_policy_id
    ON company_policy_attachments(policy_id);

CREATE TABLE IF NOT EXISTS exit_task_templates (
    id SERIAL PRIMARY KEY,
    title VARCHAR(180) NOT NULL,
    assignee_role VARCHAR(24) NOT NULL DEFAULT 'hr',
    active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS exit_assigned_tasks (
    id SERIAL PRIMARY KEY,
    exit_id INTEGER NOT NULL REFERENCES people_exit_cases(id),
    title VARCHAR(180) NOT NULL,
    assignee_role VARCHAR(24) NOT NULL,
    assignee_id INTEGER NULL REFERENCES employees(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    completion_note TEXT NOT NULL DEFAULT '',
    completed_by INTEGER NULL REFERENCES employees(id)
);
CREATE INDEX IF NOT EXISTS ix_exit_assigned_tasks_exit_id
    ON exit_assigned_tasks(exit_id);
COMMIT;
