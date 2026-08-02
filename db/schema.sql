CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE parcelle (
    id          bigserial PRIMARY KEY,
    code_insee  text NOT NULL,
    prefixe     text NOT NULL,
    section     text NOT NULL,
    numero      text NOT NULL,
    geom        geometry(Polygon, 4326) NOT NULL,
    min_lon     double precision NOT NULL,
    min_lat     double precision NOT NULL,
    max_lon     double precision NOT NULL,
    max_lat     double precision NOT NULL,
    surface_m2  double precision,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT parcelle_identifiant_unique
        UNIQUE (code_insee, prefixe, section, numero)
);

CREATE INDEX parcelle_geom_gist ON parcelle USING GIST (geom);
