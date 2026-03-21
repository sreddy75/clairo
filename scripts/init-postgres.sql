-- Clairo PostgreSQL Initialization Script
-- This script runs on first database initialization

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Note: pgvector is not included by default in postgres:16-alpine
-- For vector operations, we use Pinecone instead
-- If pgvector is needed, use: ankane/pgvector image or install extension

-- Create application schema (optional, using public for simplicity)
-- CREATE SCHEMA IF NOT EXISTS clairo;

-- Log initialization complete
DO $$
BEGIN
    RAISE NOTICE 'Clairo database initialized successfully';
END $$;
