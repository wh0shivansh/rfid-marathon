-- Initialization SQL for local PostgreSQL instance
-- This file is intended to be templated by the setup script.
-- Placeholders: __APP_USER__, __APP_PASSWORD__, __APP_DB__

CREATE ROLE "__APP_USER__" WITH LOGIN PASSWORD '__APP_PASSWORD__';
ALTER ROLE "__APP_USER__" WITH LOGIN PASSWORD '__APP_PASSWORD__';
CREATE DATABASE "__APP_DB__" OWNER "__APP_USER__";
GRANT ALL PRIVILEGES ON DATABASE "__APP_DB__" TO "__APP_USER__";
