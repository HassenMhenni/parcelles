"""API views (Django REST Framework + GeoDjango).

Routes exposed:

    GET    /health                   API and database status
    GET    /parcelles                list, filterable by attribute and by zone
    POST   /parcelles                create a parcelle from a GeoJSON Feature
    GET    /parcelles/{id}           detail of one parcelle
    PUT    /parcelles/{id}           full replacement
    PATCH  /parcelles/{id}           partial update
    DELETE /parcelles/{id}           delete
    GET    /parcelles/{id}/voisines  the parcelles touching it

"""

from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import geo
from .models import Parcelle
from .serializers import IDENTIFIER_FIELDS, ParcelleSerializer


class HealthView(APIView):
    """
    GET /health — API and database status.
    use APIView because we don't need a queryset or a serializer, we just want
    to return a simple JSON response
    """

    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version()")
            postgis = cursor.fetchone()[0]

        return Response(
            {
                "status": "ok",
                "postgis": postgis,
                "parcelles": Parcelle.objects.count(),
            }
        )


class ParcelleListCreateView(generics.ListCreateAPIView):
    """
    generics.ListCreateAPIView (DRF): a generic class that combines two mixins
    on the same collection URL:

    GET → list(): returns the serialized queryset (with pagination if configured)
    POST → create(): validates the payload via the serializer, saves it, and
    returns 201
    Everything else (PUT, DELETE) → automatically returns 405
    All you need to do is provide the serializer_class and the queryset (or
    get_queryset()); the rest of the HTTP cycle is handled automatically.

    this is the /parcelles endpoint.

    GET /parcelles → paginated list (200 per page, max 1,000), filterable by
    code_insee, section, and geographic area (bbox=... or zone={GeoJSON}, with
    mode=intersects)
    POST /parcelles → creates a parcelle via ParcelleSerializer


    """

    serializer_class = ParcelleSerializer

    def get_queryset(self):
        # all the parcelles with area already calculated in SQL
        queryset = geo.parcelles_with_area()
        for field in IDENTIFIER_FIELDS:
            # self.request.query_params is {"section": "ab", "numero": "12"}
            # if GET /parcelles?section=ab&numero=12
            value = self.request.query_params.get(field, "").strip()
            if not value:
                continue
            if field == "section":
                value = value.upper()
            queryset = queryset.filter(**{field: value})

        return self._filter_by_zone(queryset)

    def _filter_by_zone(self, queryset):
        """Apply ?bbox= / ?zone= (+ ?mode=) if present, else return as is.

        GET /parcelles?bbox=1.42,43.59,1.46,43.61
        GET /parcelles?zone={"type":"Polygon","coordinates":[...]}?mode=intersects
        """
        params = self.request.query_params

        bbox = params.get("bbox", "").strip()
        zone = params.get("zone", "").strip()

        if bbox and zone:
            raise ValidationError(
                {"zone": ["Specify either `bbox` or `zone`, not both."]}
            )

        mode = params.get("mode", "").strip() or geo.DEFAULT_ZONE_MODE

        if not bbox and not zone:
            if params.get("mode"):
                raise ValidationError(
                    {"mode": ["`mode` only applies together with `bbox` or `zone`."]}
                )
            return queryset

        try:
            geo.validate_mode(mode)
        except geo.InvalidGeometry as error:
            raise ValidationError({"mode": [str(error)]}) from error

        # Each error is filed under the parameter that caused it, so a client
        # reading the response knows which one to fix.
        field = "bbox" if bbox else "zone"
        try:
            raw = geo.read_bbox(bbox) if bbox else geo.read_geojson(zone)
            geometry = geo.validate_zone(raw)
        except geo.InvalidGeometry as error:
            raise ValidationError({field: [str(error)]}) from error

        return geo.in_zone(queryset, geometry, mode)


class ParcelleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET / PUT / PATCH / DELETE /parcelles/{id}.
    """

    serializer_class = ParcelleSerializer

    def get_queryset(self):
        return geo.parcelles_with_area()


class ParcelleNeighboursView(generics.ListAPIView):
    """GET /parcelles/{id}/voisines — the parcelles touching this one.
        Answers 404 if the parcelle does not exist
    """

    serializer_class = ParcelleSerializer

    def get_queryset(self):
        parcelle = get_object_or_404(Parcelle, pk=self.kwargs["pk"])
        return geo.neighbours(parcelle)
