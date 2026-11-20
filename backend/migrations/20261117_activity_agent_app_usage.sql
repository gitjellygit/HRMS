-- Aggregate foreground executable usage, no URLs/window titles/keystrokes.
ALTER TABLE activity_agent_devices ADD COLUMN IF NOT EXISTS app_usage_json TEXT NOT NULL DEFAULT '{}';
