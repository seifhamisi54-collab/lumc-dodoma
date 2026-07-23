#!/bin/bash
# Runs once on first PostGIS container start.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE SCHEMA IF NOT EXISTS boundaries;
    CREATE SCHEMA IF NOT EXISTS admin;
    CREATE SCHEMA IF NOT EXISTS demographic;
    CREATE SCHEMA IF NOT EXISTS infrastructure;
    CREATE SCHEMA IF NOT EXISTS landuse;
    CREATE SCHEMA IF NOT EXISTS detailed_planning;
EOSQL

# Second DB used by Detailed Planning / Migogoro
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    SELECT 'CREATE DATABASE "DETAILED PLANNNING "'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'DETAILED PLANNNING ')\\gexec
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "DETAILED PLANNNING " <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE SCHEMA IF NOT EXISTS detailed_planning;
EOSQL

echo "PostGIS databases and schemas ready."
