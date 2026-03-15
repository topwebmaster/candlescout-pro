-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Performance settings for TimescaleDB
ALTER SYSTEM SET shared_preload_libraries = 'timescaledb,pg_stat_statements';
