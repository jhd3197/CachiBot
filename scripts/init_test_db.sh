#!/bin/bash
# Create the test database with pgvector extension.
#
# Usage (after starting the PostgreSQL container):
#   docker exec cachibot-db bash /scripts/init_test_db.sh
#
# Or from the host:
#   docker exec cachibot-db psql -U cachibot -d postgres \
#       -c "CREATE DATABASE cachibot_test OWNER cachibot;"
#   docker exec cachibot-db psql -U cachibot -d cachibot_test \
#       -c "CREATE EXTENSION IF NOT EXISTS vector;"

set -e

psql -U cachibot -d postgres -c "SELECT 1 FROM pg_database WHERE datname = 'cachibot_test'" \
    | grep -q 1 || psql -U cachibot -d postgres -c "CREATE DATABASE cachibot_test OWNER cachibot;"

psql -U cachibot -d cachibot_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "Test database 'cachibot_test' is ready with pgvector extension."
