ALTER TABLE profiles ADD COLUMN IF NOT EXISTS allowed_modules jsonb DEFAULT '[]'::jsonb;
