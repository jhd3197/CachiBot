-- Enable pgvector extension for embedding storage and vector similarity search.
-- This script is run automatically by PostgreSQL on first container startup
-- via the docker-entrypoint-initdb.d mechanism.

CREATE EXTENSION IF NOT EXISTS vector;
