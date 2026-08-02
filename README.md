# Cadastral parcelles API

A small business API for cadastral parcelles, built on **PostGIS**. Geometries go
in and out as **GeoJSON**, and the geographic rules (non-overlap, adjacency, zone
filtering, area computation) are delegated to the spatial database rather than
reimplemented in Python.

Dataset: the 8,521 parcelles of central Toulouse (DGFiP / Etalab).

## Getting started

Requires PostgreSQL ≥ 14 with **PostGIS** ≥ 3 (a role allowed to create the
extension), Python ≥ 3.11, and the libraries GeoDjango loads at startup —
`gdal-bin libgdal-dev` on Debian/Ubuntu.

Create a `.env` at the root. It is not in the repository — it holds the database
password and the secret key — and it is read at startup by `config/settings.py`:

```bash
POSTGRES_DB=parcelles
POSTGRES_USER=parcelles
POSTGRES_PASSWORD=...
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

DJANGO_DEBUG=1
DJANGO_SECRET_KEY=dev-insecure-change-me
DJANGO_ALLOWED_HOSTS=*
```

Then:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py init_db            # extension + schema + CSV load
python manage.py init_db --reset    # start again from an empty table

python manage.py migrate            # admin tables only (auth, sessions, logs)
python manage.py createsuperuser    # an account for /admin

python manage.py runserver
curl -s localhost:8000/health
# {"status":"ok","postgis":"3.6 USE_GEOS=1 ...","parcelles":8521}
```

`init_db` applies `db/schema.sql` as is, then loads `data/parcelles.csv` in
batches. `migrate` never touches `parcelle` — the model is `managed = False` — so
the API alone only needs `init_db`.

## Routes

| Method | Route | Effect |
|---|---|---|
| `GET` | `/health` | API status, PostGIS version, parcelle count |
| `GET` | `/parcelles` | list, filterable by attribute and by zone |
| `POST` | `/parcelles` | create a parcelle |
| `GET` | `/parcelles/{id}` | detail |
| `PUT` / `PATCH` | `/parcelles/{id}` | full replacement / partial update |
| `DELETE` | `/parcelles/{id}` | delete |
| `GET` | `/parcelles/{id}/voisines` | the parcelles touching it |
| | `/admin/` | back-office: same table, geometry edited on a map |

## Representation

A parcelle is a **GeoJSON Feature** (RFC 7946). The same shape goes in and comes
out: the body of a `GET` can be replayed straight into a `POST`.

```json
{
  "type": "Feature",
  "id": 4211,
  "bbox": [1.4451, 43.6042, 1.4462, 43.6051],
  "geometry": {"type": "Polygon", "coordinates": [[[1.4451, 43.6042], "..."]]},
  "properties": {
    "code_insee": "31555", "prefixe": "806", "section": "AB", "numero": "139",
    "surface_m2": 15774.0,
    "created_at": "2026-07-26T19:12:03Z", "updated_at": "2026-07-26T19:12:03Z"
  }
}
```

`id`, `bbox` and `surface_m2` are **computed**: ignored on input, always present
on output. Property names, the `/voisines` route and the error codes keep their
French spelling — they are the published contract.

Lists return a paginated `FeatureCollection` (200 per page, 1,000 max):
`{"type": "FeatureCollection", "count": 8521, "features": [...]}`.

## Filters

```bash
# by attribute (section is case-insensitive)
curl -s 'localhost:8000/parcelles?section=AB&code_insee=31555'

# by zone: map rectangle
curl -s 'localhost:8000/parcelles?bbox=1.4400,43.6000,1.4450,43.6050'

# by zone: any GeoJSON polygon
curl -s --get localhost:8000/parcelles \
  --data-urlencode 'zone={"type":"Polygon","coordinates":[[[1.44,43.60],[1.44,43.61],[1.45,43.61],[1.45,43.60],[1.44,43.60]]]}'

# include parcelles only partly inside the zone
curl -s 'localhost:8000/parcelles?bbox=1.44,43.60,1.45,43.605&mode=intersects'
```

`bbox` and `zone` are two spellings of the same thing and cannot be combined with
each other; both combine with the attribute filters and with pagination.

## Status codes

| Code | When |
|---|---|
| `200` / `201` / `204` | read or update / create / delete |
| `400` | malformed body or parameter: unreadable GeoJSON, self-intersecting geometry, `code_insee` out of format, unknown `mode` |
| `404` | no such parcelle |
| `405` | verb not applicable to the route (`DELETE /parcelles`) |
| `409` | conflict with the current state: identifier already taken, or overlap |

The 400 / 409 split is deliberate: a 409 flags a well-formed request that clashes
with what is currently stored, and the body names what blocks it so the client can
act.

```json
{"code": "chevauchement",
 "detail": "The geometry overlaps 1 existing parcelle(s)…",
 "parcelles_en_conflit": [{"id": 8522, "identifiant": "31555-999-ZZ-1"}]}
```
