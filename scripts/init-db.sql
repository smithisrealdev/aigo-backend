-- ===========================================
-- AiGo Database Initialization Script
-- PostgreSQL 16
-- ===========================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram similarity for fuzzy search
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN index support
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- Remove accents for search

-- Create custom types (if not exists)
DO $$
BEGIN
    -- Itinerary status enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'itinerary_status') THEN
        CREATE TYPE itinerary_status AS ENUM (
            'draft',
            'planned',
            'confirmed',
            'in_progress',
            'completed',
            'cancelled'
        );
    END IF;

    -- Activity category enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'activity_category') THEN
        CREATE TYPE activity_category AS ENUM (
            'transportation',
            'accommodation',
            'dining',
            'sightseeing',
            'entertainment',
            'shopping',
            'wellness',
            'business',
            'other'
        );
    END IF;
END$$;

-- ===========================================
-- Performance tuning for development
-- ===========================================
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '768MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '8MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '80MB';
ALTER SYSTEM SET max_wal_size = '1GB';

-- ===========================================
-- Create helper functions
-- ===========================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function for soft delete
CREATE OR REPLACE FUNCTION soft_delete()
RETURNS TRIGGER AS $$
BEGIN
    NEW.deleted_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ===========================================
-- Grant permissions
-- ===========================================
GRANT ALL PRIVILEGES ON DATABASE aigo_db TO aigo;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aigo;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aigo;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO aigo;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO aigo;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO aigo;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO aigo;

-- ===========================================
-- Create test database for testing
-- ===========================================
-- This will be used for running tests
SELECT 'CREATE DATABASE aigo_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aigo_test')\gexec

-- Grant permissions on test database
GRANT ALL PRIVILEGES ON DATABASE aigo_test TO aigo;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE '✅ AiGo database initialization completed successfully!';
    RAISE NOTICE '📦 Extensions enabled: uuid-ossp, pg_trgm, btree_gin, unaccent';
    RAISE NOTICE '🎯 Custom types created: itinerary_status, activity_category';
    RAISE NOTICE '⚡ Performance settings configured for development';
END$$;
