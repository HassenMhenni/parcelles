import json

from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.functions import Area
from django.contrib.gis.gdal import GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry, Polygon
from django.db.models.functions import Cast

from .models import Parcelle

# Cast converts the geometry (lon/lat) to the geography type
# Area computes the area of the geography type in square metres
# SELECT ..., ST_Area(CAST("parcelle"."geom" AS geography)) AS "computed_area"
# FROM "parcelle" ORDER BY "id";
AREA_M2 = Area(Cast("geom", GeometryField(srid=4326, geography=True)))

OVERLAP_MASK = "T********"

SRID = 4326
ZONE_MODES = ("within", "intersects")
DEFAULT_ZONE_MODE = "within"

ZONE_TYPES = ("Polygon", "MultiPolygon")

GEOMETRY_TOLERANCE = 1e-9


class InvalidGeometry(ValueError):
    """A geometry PostGIS would refuse, or that makes no sense as a parcelle."""


def parcelles_with_area():
    """
    #SELECT ..., ST_Area(CAST("parcelle"."geom" AS geography)) AS "computed_area"
    #FROM "parcelle" ORDER BY "id";

    `annotate` adds a `computed_area` column to the query; the serializer
    falls back on it when the official `surface_m2` is NULL, for parcelles
    created through the API.
    """
    return Parcelle.objects.annotate(computed_area=AREA_M2).order_by("id")


def validate_polygon(geom):
    """Return the geometry ready to be stored, or raise `InvalidGeometry`.
        when we arrive here geom is not a json anymore it is a GEOSGeometry object
        geom.geom_type -> "Polygon" or "MultiPolygon" or "Point" or "LineString"
            or "MultiLineString" or "GeometryCollection"...
        geom.srid -> 4326 or None or another number, meaning the geometry is in
            another coordinate system than WGS84
        geom.valid -> True or False, meaning the geometry is valid or not
        geom.empty -> True or False, meaning the geometry is empty or not
        geom.valid_reason -> a string that explains why the geometry is invalid
    """

    # a parcelle should be a polygon
    if geom.geom_type != "Polygon":
        raise InvalidGeometry(
            f"A parcelle is a single polygon; geometry received: {geom.geom_type}."
        )

    # 2. srid should be 4326 (WGS84) or None (no SRID). If it is None, we set it
    # to 4326. If it is not 4326, we raise an error.
    if geom.srid is None:
        geom.srid = SRID
    elif geom.srid != SRID:
        raise InvalidGeometry(
            f"Geometry expected in WGS84 (EPSG:{SRID}), received in EPSG:{geom.srid}."
        )

    if geom.empty:
        raise InvalidGeometry("The geometry is empty.")

    # Valid means that the data is correct but topologically it is not correct,
    # for example a polygon that intersects itself.
    if not geom.valid:
        raise InvalidGeometry(f"Invalid geometry: {geom.valid_reason}.")

    return geom


def same_geometry(one, other):
    """Return True if the two geometries are equal, within a tolerance.
    """
    return one.equals(other) or one.equals_exact(other, GEOMETRY_TOLERANCE)


def overlaps(geom, exclude=None):
    """
    2 parcelles can't overlap, they can just touch borders
    geom__bboverlaps
    matrix DE-9IM
    every geometry is composed of 3 parts: interior, boundary, exterior
    every case explains the intersection between 2 geometries A and B
            I(B)    B(B)    E(B)
    I(A)    pos. 1  pos. 2  pos. 3
    B(A)    pos. 4  pos. 5  pos. 6
    E(A)    pos. 7  pos. 8  pos. 9

    every case can have the following values
    F = false, the intersection is empty
    0 = 1 or more points
    1 = 1 or more lines
    2 = a surface
    T = true, the intersection is not empty it can be 0 1 2
    * = any value
    """
    # https://docs.djangoproject.com/en/6.0/ref/contrib/gis/geoquerysets/#relate
    # geom__bboverlaps compares bounding boxes of geometries and returns true if they overlap
    # it is very fast but can return false positives
    # geom__relate: once we have a few candidates we check if it really overlaps
    queryset = Parcelle.objects.filter(geom__bboverlaps=geom).filter(
        geom__relate=(geom, OVERLAP_MASK)
    )

    if exclude is not None:
        queryset = queryset.exclude(pk=exclude)

    return queryset.order_by("id")


# --------------------------------------------------------------- zone filter


def read_geojson(text):
    """Parse GeoJSON text into a geometry, or raise `InvalidGeometry`.

    Used for the geometries that arrive outside a request body — the zone of the
    map, passed in the query string. The ones inside a body go through DRF's
    `GeometryField` instead.

    `GEOSGeometry` also accepts WKT and (HEX)EWKB. We check the string parses as
    JSON first, so that the API keeps the single input format it advertises and
    a typo gets "invalid JSON" rather than GEOS's parser error.
    """
    try:
        json.loads(text)
    except ValueError as error:
        raise InvalidGeometry(f"Unreadable zone: invalid JSON ({error}).") from error

    try:
        return GEOSGeometry(text)
    except (GEOSException, GDALException, ValueError, TypeError) as error:
        raise InvalidGeometry(f"Unreadable zone: {error}") from error


def read_bbox(text):
    """Parse `min_lon,min_lat,max_lon,max_lat` into a rectangle.

    A shorthand for the common case: a map viewport is a rectangle, and spelling
    it as a five-point GeoJSON polygon in a URL is needlessly verbose.
    """
    parts = text.split(",")
    if len(parts) != 4:
        raise InvalidGeometry(
            "Bbox expected as min_lon,min_lat,max_lon,max_lat "
            f"(4 numbers, {len(parts)} received)."
        )

    try:
        min_lon, min_lat, max_lon, max_lat = (float(part) for part in parts)
    except ValueError as error:
        raise InvalidGeometry(f"Bbox expected: 4 comma-separated numbers ({error}).") from error

    # A rectangle with no width or no height has an empty interior: nothing can
    # be within it, so the answer would always be empty. Say so instead.
    if min_lon >= max_lon or min_lat >= max_lat:
        raise InvalidGeometry(
            "Empty bbox: min_lon < max_lon and min_lat < max_lat are required "
            f"(received {min_lon},{min_lat},{max_lon},{max_lat})."
        )

    rectangle = Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))
    rectangle.srid = SRID
    return rectangle


def validate_zone(geom):
    """Return the zone geometry ready to filter with, or raise `InvalidGeometry`.

    Same checks as `validate_polygon`, minus the "one single polygon" rule: a
    zone may legitimately be a MultiPolygon (two separate districts, an island).
    """
    if geom.geom_type not in ZONE_TYPES:
        raise InvalidGeometry(
            "A zone is a surface (Polygon or MultiPolygon); "
            f"geometry received: {geom.geom_type}."
        )

    if geom.srid is None:
        geom.srid = SRID
    elif geom.srid != SRID:
        raise InvalidGeometry(
            f"Zone expected in WGS84 (EPSG:{SRID}), received in EPSG:{geom.srid}."
        )

    if geom.empty:
        raise InvalidGeometry("The zone is empty.")

    # An invalid zone (a self-crossing ring) makes PostGIS raise mid-query,
    # which would surface as a 500. Caught here, it is a 400.
    if not geom.valid:
        raise InvalidGeometry(f"Invalid zone: {geom.valid_reason}.")

    return geom


def validate_mode(mode):
    """Check the requested spatial predicate, or raise `InvalidGeometry`.

    Whitelisted rather than passed through: the value is interpolated into a
    queryset lookup (`geom__<mode>`), so it must never come straight from the
    query string.
    """
    if mode not in ZONE_MODES:
        raise InvalidGeometry(
            f"Unknown mode « {mode} »; accepted values: {', '.join(ZONE_MODES)}."
        )

    return mode


def in_zone(queryset, zone, mode=DEFAULT_ZONE_MODE):
    """Restrict `queryset` to the parcelles matching `zone` under `mode`."""
    return queryset.filter(**{f"geom__{mode}": zone})


# ----------------------------------------------------------------- adjacency


def neighbours(parcelle):
    """Return the parcelles that touch the given one, excluding itself.
       use sql ST_Touches to find parcelles that touch the given parcelle
       https://postgis.net/docs/ST_Touches.html
    """
    queryset = parcelles_with_area().filter(geom__touches=parcelle.geom)
    return queryset.exclude(pk=parcelle.pk)
