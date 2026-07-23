-- =============================================================================
-- DETAILED PLANNING — PostgreSQL 13 + PostGIS
-- =============================================================================
-- PostgreSQL 13: C:\Program Files\PostgreSQL\13\
-- Port: 5433 (POSTGRES13)
-- Database: "DETAILED PLANNNING "  (jina halisi kwenye server yako)
--
-- JINSI YA KUENDESHA KWENYE pgAdmin 4 (PostgreSQL 13):
--   1. Fungua pgAdmin → Servers → PostgreSQL 13 → Databases
--   2. Chagua database "DETAILED PLANNNING"
--   3. Tools → Query Tool
--   4. File → Open → chagua faili hili
--   5. Bonyeza Execute (F5)
--
-- AU kwa psql (PowerShell):
--   $env:PGPASSWORD='1701'
--   & "C:\Program Files\PostgreSQL\13\bin\psql.exe" -h localhost -p 5433 -U postgres -d "DETAILED PLANNNING " -f scripts/create_detailed_planning_tables.sql
--
-- Chaguo la pili — tumia schema ndani ya tanzania_gis_db:
--   Badilisha \c line hapa chini kuwa: \c tanzania_gis_db
-- =============================================================================

\c "DETAILED PLANNNING "

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS detailed_planning;
SET search_path TO detailed_planning, public;

COMMENT ON SCHEMA detailed_planning IS
    'Mipaka, shapefile, ripoti na detailed planning kwa kijiji — LUMC Tanzania';

-- -----------------------------------------------------------------------------
-- 1. MIPAKA YA WILAYA (District Boundaries)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detailed_planning.district_boundaries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    region_name     VARCHAR(255) NOT NULL,
    district_name   VARCHAR(255) NOT NULL,
    geom            geometry(MultiPolygon, 32736),
    shapefile_name  VARCHAR(500),
    area_ha         DOUBLE PRECISION,
    created_by_id   INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (region_name, district_name)
);

COMMENT ON TABLE detailed_planning.district_boundaries IS 'Mipaka ya wilaya — District boundaries';
CREATE INDEX IF NOT EXISTS idx_dp_dist_region ON detailed_planning.district_boundaries (region_name, district_name);
CREATE INDEX IF NOT EXISTS idx_dp_dist_geom ON detailed_planning.district_boundaries USING GIST (geom);

-- -----------------------------------------------------------------------------
-- 2. MIPAKA YA KATA (Ward Boundaries)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detailed_planning.ward_boundaries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    region_name     VARCHAR(255) NOT NULL,
    district_name   VARCHAR(255) NOT NULL,
    ward_name       VARCHAR(255) NOT NULL,
    geom            geometry(MultiPolygon, 32736),
    shapefile_name  VARCHAR(500),
    area_ha         DOUBLE PRECISION,
    created_by_id   INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (region_name, district_name, ward_name)
);

COMMENT ON TABLE detailed_planning.ward_boundaries IS 'Mipaka ya kata — Ward boundaries';
CREATE INDEX IF NOT EXISTS idx_dp_ward_loc ON detailed_planning.ward_boundaries (region_name, district_name, ward_name);
CREATE INDEX IF NOT EXISTS idx_dp_ward_geom ON detailed_planning.ward_boundaries USING GIST (geom);

-- -----------------------------------------------------------------------------
-- 3. MIPAKA YA KIJIJI (Village Boundaries)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detailed_planning.village_boundaries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    region_name     VARCHAR(255) NOT NULL,
    district_name   VARCHAR(255) NOT NULL,
    ward_name       VARCHAR(255) NOT NULL,
    village_name    VARCHAR(255) NOT NULL,
    geom            geometry(MultiPolygon, 32736),
    shapefile_name  VARCHAR(500),
    area_ha         DOUBLE PRECISION,
    created_by_id   INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (region_name, district_name, ward_name, village_name)
);

COMMENT ON TABLE detailed_planning.village_boundaries IS 'Mipaka ya kijiji — Village boundaries';
CREATE INDEX IF NOT EXISTS idx_dp_vill_loc ON detailed_planning.village_boundaries (region_name, district_name, ward_name, village_name);
CREATE INDEX IF NOT EXISTS idx_dp_vill_geom ON detailed_planning.village_boundaries USING GIST (geom);

-- -----------------------------------------------------------------------------
-- 4. MIPANGO YA KIJIJI (Village Detailed Plans — takwimu)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detailed_planning.village_plans (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    region_name             VARCHAR(255) NOT NULL,
    district_name           VARCHAR(255) NOT NULL,
    ward_name               VARCHAR(255) NOT NULL,
    village_name            VARCHAR(255) NOT NULL,
    total_landowners        INTEGER NOT NULL DEFAULT 0,
    female_landowners       INTEGER NOT NULL DEFAULT 0,
    male_landowners         INTEGER NOT NULL DEFAULT 0,
    children_under_18       INTEGER NOT NULL DEFAULT 0,
    identified_parcels      INTEGER NOT NULL DEFAULT 0,
    unidentified_parcels    INTEGER NOT NULL DEFAULT 0,
    plan_status             VARCHAR(50) NOT NULL DEFAULT 'draft',
    plan_year               INTEGER,
    notes                   TEXT,
    created_by_id           INTEGER,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (region_name, district_name, ward_name, village_name)
);

COMMENT ON TABLE detailed_planning.village_plans IS 'Takwimu za detailed planning kwa kijiji';
CREATE INDEX IF NOT EXISTS idx_dp_vplan_loc ON detailed_planning.village_plans (region_name, district_name, ward_name, village_name);

-- -----------------------------------------------------------------------------
-- 5. VIWANJA (Planning Parcels — namba za kiwanja)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detailed_planning.planning_parcels (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parcel_number       VARCHAR(100) NOT NULL UNIQUE,
    plot_sequence       INTEGER NOT NULL DEFAULT 0,
    region_name         VARCHAR(255) NOT NULL,
    district_name       VARCHAR(255) NOT NULL,
    ward_name           VARCHAR(255) NOT NULL,
    village_name        VARCHAR(255) NOT NULL,
    geom                geometry(MultiPolygon, 32736),
    area_ha             DOUBLE PRECISION,
    is_identified       BOOLEAN NOT NULL DEFAULT FALSE,
    owner_name          VARCHAR(255),
    owner_gender        CHAR(1),
    owner_age_category  VARCHAR(10),
    owner_is_landowner  BOOLEAN NOT NULL DEFAULT TRUE,
    village_plan_id     UUID REFERENCES detailed_planning.village_plans(id) ON DELETE SET NULL,
    notes               TEXT,
    created_by_id       INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE detailed_planning.planning_parcels IS 'Viwanja vya detailed planning — DP/MKO/WIL/KAT/KIJ/0001';
CREATE INDEX IF NOT EXISTS idx_dp_parcel_loc ON detailed_planning.planning_parcels (region_name, district_name, ward_name, village_name);
CREATE INDEX IF NOT EXISTS idx_dp_parcel_num ON detailed_planning.planning_parcels (parcel_number);
CREATE INDEX IF NOT EXISTS idx_dp_parcel_id ON detailed_planning.planning_parcels (is_identified);
CREATE INDEX IF NOT EXISTS idx_dp_parcel_geom ON detailed_planning.planning_parcels USING GIST (geom);

-- -----------------------------------------------------------------------------
-- 6. SHAPEFILES (Uhifadhi wa faili za shapefile)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detailed_planning.planning_shapefiles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title               VARCHAR(255) NOT NULL,
    boundary_level      VARCHAR(20) NOT NULL
        CHECK (boundary_level IN ('district', 'ward', 'village', 'parcel', 'landuse', 'other')),
    region_name         VARCHAR(255) NOT NULL,
    district_name       VARCHAR(255),
    ward_name           VARCHAR(255),
    village_name        VARCHAR(255),
    original_filename   VARCHAR(500) NOT NULL,
    stored_filename     VARCHAR(500) NOT NULL,
    file_path           VARCHAR(1000) NOT NULL,
    file_format         VARCHAR(20) NOT NULL DEFAULT 'zip'
        CHECK (file_format IN ('zip', 'shp', 'geojson', 'gpkg', 'kml')),
    file_size_bytes     BIGINT,
    feature_count       INTEGER,
    srid                INTEGER NOT NULL DEFAULT 32736,
    geom                geometry(MultiPolygon, 32736),
    status              VARCHAR(20) NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'processed', 'failed', 'archived')),
    district_boundary_id UUID REFERENCES detailed_planning.district_boundaries(id) ON DELETE SET NULL,
    ward_boundary_id    UUID REFERENCES detailed_planning.ward_boundaries(id) ON DELETE SET NULL,
    village_boundary_id UUID REFERENCES detailed_planning.village_boundaries(id) ON DELETE SET NULL,
    village_plan_id     UUID REFERENCES detailed_planning.village_plans(id) ON DELETE SET NULL,
    notes               TEXT,
    uploaded_by_id      INTEGER,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE detailed_planning.planning_shapefiles IS 'Shapefile zilizopakiwa — mipaka na tabaka za mpango';
CREATE INDEX IF NOT EXISTS idx_dp_shp_level ON detailed_planning.planning_shapefiles (boundary_level);
CREATE INDEX IF NOT EXISTS idx_dp_shp_loc ON detailed_planning.planning_shapefiles (region_name, district_name, ward_name, village_name);
CREATE INDEX IF NOT EXISTS idx_dp_shp_geom ON detailed_planning.planning_shapefiles USING GIST (geom);

-- -----------------------------------------------------------------------------
-- 7. RIPOTI (Reports — PDF, Excel, n.k.)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detailed_planning.planning_reports (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title               VARCHAR(255) NOT NULL,
    report_type         VARCHAR(30) NOT NULL DEFAULT 'plan_summary'
        CHECK (report_type IN ('plan_summary', 'parcel_list', 'boundary_map', 'statistics', 'pdf', 'excel', 'other')),
    region_name         VARCHAR(255) NOT NULL,
    district_name       VARCHAR(255),
    ward_name           VARCHAR(255),
    village_name        VARCHAR(255),
    report_year         INTEGER,
    original_filename   VARCHAR(500) NOT NULL,
    stored_filename     VARCHAR(500) NOT NULL,
    file_path           VARCHAR(1000) NOT NULL,
    file_format         VARCHAR(20) NOT NULL DEFAULT 'pdf'
        CHECK (file_format IN ('pdf', 'docx', 'xlsx', 'csv', 'html')),
    file_size_bytes     BIGINT,
    status              VARCHAR(20) NOT NULL DEFAULT 'generated'
        CHECK (status IN ('draft', 'generated', 'approved', 'archived')),
    village_plan_id     UUID REFERENCES detailed_planning.village_plans(id) ON DELETE SET NULL,
    shapefile_id        UUID REFERENCES detailed_planning.planning_shapefiles(id) ON DELETE SET NULL,
    summary             TEXT,
    notes               TEXT,
    generated_by_id     INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE detailed_planning.planning_reports IS 'Ripoti za detailed planning — PDF, Excel, n.k.';
CREATE INDEX IF NOT EXISTS idx_dp_rep_type ON detailed_planning.planning_reports (report_type);
CREATE INDEX IF NOT EXISTS idx_dp_rep_loc ON detailed_planning.planning_reports (region_name, district_name, ward_name, village_name);
CREATE INDEX IF NOT EXISTS idx_dp_rep_year ON detailed_planning.planning_reports (report_year);

-- -----------------------------------------------------------------------------
-- Trigger: sasisha updated_at
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION detailed_planning.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'district_boundaries', 'ward_boundaries', 'village_boundaries',
        'village_plans', 'planning_parcels',
        'planning_shapefiles', 'planning_reports'
    ]
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%s_updated ON detailed_planning.%I;
             CREATE TRIGGER trg_%s_updated
             BEFORE UPDATE ON detailed_planning.%I
             FOR EACH ROW EXECUTE PROCEDURE detailed_planning.set_updated_at();',
            t, t, t, t
        );
    END LOOP;
END $$;

-- -----------------------------------------------------------------------------
-- Muhtasari
-- -----------------------------------------------------------------------------
SELECT 'Schema detailed_planning imeundwa kwa mafanikio!' AS ujumbe;
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'detailed_planning'
ORDER BY table_name;
