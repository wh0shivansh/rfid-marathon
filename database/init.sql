-- Initialization SQL for local Postgres container
-- Creates user `rfid`, database `rfid_db`, and grants privileges.

DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'rfid') THEN
       CREATE ROLE rfid WITH LOGIN PASSWORD 'InnoRfidPass';
   END IF;
END
$$;

-- Create database if it doesn't exist
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'rfid_db') THEN
       PERFORM pg_catalog.set_config('search_path', '', false);
       CREATE DATABASE rfid_db OWNER rfid;
   END IF;
END
$$;

-- Add any additional schema/init statements below if needed.
