"""Parcelle serialization in GeoJSON format (RFC 7946).
source https://datatracker.ietf.org/doc/html/rfc7946
A parcelle is represented as a `Feature` object:
    {
      "type": "Feature",
      "id": 1,
      "bbox": [min_lon, min_lat, max_lon, max_lat],
      "geometry": {"type": "Polygon", "coordinates": [[[1.45, 43.61], ...]]},
      "properties": {
        "code_insee": "31555", "prefixe": "806", "section": "AB", "numero": "139",
        "surface_m2": 15774.0,
        "created_at": "...", "updated_at": "..."
      }
    }

The property names are the published API contract and the column names of the
`parcelle` table, so they keep their cadastral spelling.
"""

from datetime import timezone as tz

from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework.settings import api_settings
# GeometryField: GEOSGeometry <-> dict GeoJSON {"type": "Polygon", "coordinates": [...]}
# because DRF dont know how to serialize GEOSGeometry objects like PolygonField
# in our case
from rest_framework_gis.fields import GeometryField

from . import geo
from .exceptions import Conflict
from .models import Parcelle

IDENTIFIER_FIELDS = ("code_insee", "prefixe", "section", "numero")

#   code_insee  5 characters — 2 for the département, 3 for the commune.
#               Toulouse is written 31555
#   prefixe     3 digits
#   section     1 or 2 characters.
#   numero      up to 4 digits.
IDENTIFIER_VALIDATORS = {
    "code_insee": RegexValidator(
        r"^(2[AB]|[0-9]{2})[0-9]{3}$",
        "INSEE code expected: 5 characters, for example 31555 or 2A004.",
    ),
    "prefixe": RegexValidator(
        r"^[0-9]{3}$",
        "Prefix expected: 3 digits, 000 when no commune was absorbed.",
    ),
    "section": RegexValidator(
        r"^[0-9A-Z]{1,2}$",
        "Section expected: 1 or 2 characters, for example AB.",
    ),
    "numero": RegexValidator(
        r"^[0-9]{1,4}$",
        "Number expected: 1 to 4 digits.",
    ),
}


class ParcelleSerializer(serializers.ModelSerializer):
    """A `Parcelle` <-> a GeoJSON `Feature`."""

    geometry = GeometryField(source="geom")

    created_at = serializers.DateTimeField(default_timezone=tz.utc, read_only=True)
    updated_at = serializers.DateTimeField(default_timezone=tz.utc, read_only=True)

    class Meta:
        model = Parcelle
        fields = ("geometry", *IDENTIFIER_FIELDS, "created_at", "updated_at")

        # validator empty because the unique conflict will do 400 and i want it to be 409 conflict
        # so i tell django im going to handle it myself in the validate method
        validators = []

        # add a condition for a field without editing it , in order to validate
        # the 4 fields of the business key, used for post if false error 404
        # example "code_insee": {"validators": [RegexValidator(r"^(2[AB]|[0-9]{2})[0-9]{3}$",)}
        extra_kwargs = {
            field: {"validators": [validator]}
            for field, validator in IDENTIFIER_VALIDATORS.items()
        }

    # ------------------------------------------------------------------ read

    def to_representation(self, instance):
        """Build the GeoJSON Feature.
        """
        properties = {field: getattr(instance, field) for field in IDENTIFIER_FIELDS}
        properties["surface_m2"] = self._area(instance)
        properties["created_at"] = self.fields["created_at"].to_representation(
            instance.created_at
        )
        properties["updated_at"] = self.fields["updated_at"].to_representation(
            instance.updated_at
        )

        return {
            "type": "Feature",
            "id": instance.pk,
            "bbox": instance.bbox,
            "geometry": self.fields["geometry"].to_representation(instance.geom),
            "properties": properties,
        }

    @staticmethod
    def _area(instance):
        """
        Return the area of a parcelle in square metres.
        """
        if instance.surface_m2 is not None:
            return instance.surface_m2

        # computed is a django.contrib.gis.measure.Area
        computed = getattr(instance, "computed_area", None)
        if computed is None:
            return None
        # .sq_m transform the area object to a float in square metres, round to 1 decimal place
        return round(computed.sq_m, 1)

    # ----------------------------------------------------------------- write

    def to_internal_value(self, data):
        """used for POST and PUT , geojson to GEOSGeometry dict
        """
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                # NON_FIELD_ERRORS_KEY can be changed in settings.py
                # REST_FRAMEWORK = {"NON_FIELD_ERRORS_KEY": "name wanted to be used"}
                # default is 'non_field_errors'
                # https://www.django-rest-framework.org/api-guide/settings/
                {api_settings.NON_FIELD_ERRORS_KEY: ["Expected a GeoJSON Feature object."]}
            )

        # type should be Feature
        received_type = data.get("type")
        if received_type is not None and received_type != "Feature":
            raise serializers.ValidationError(
                {"type": [f"Expected « Feature », received « {received_type} »."]}
            )

        # properties should be a dict, if not raise a validation error
        properties = data.get("properties")
        if properties is None:
            properties = {}
        elif not isinstance(properties, dict):
            raise serializers.ValidationError(
                {"properties": ["Expected an object holding the parcelle attributes."]}
            )

        # we put geometry and properties in flat either to get them or send an
        # error if they are empty since in the model they are non nullable, so if
        # they are empty we will get an error when we try to save the instance
        flat = {}

        if "geometry" in data:
            flat["geometry"] = data["geometry"]

        for field in IDENTIFIER_FIELDS:
            if field in properties:
                flat[field] = self._normalize(field, properties[field])

        return super().to_internal_value(flat)

    # staticmethod because we don't need to access the instance of the class,
    # we just need to access the method itself
    @staticmethod
    def _normalize(field, value):
        """
        strip and upper for section
        """
        # if the value is not a string return it as is and the regex validator will catch it later
        if not isinstance(value, str):
            return value

        value = value.strip()
        return value.upper() if field == "section" else value

    # -------------------------------------------------------------- validate

    def _final_value(self, attrs, field):
        """
        Inside a PATCH , user send the fields he want to update
        ex attrs = {"geom": <new Polygon>}
        """
        if field in attrs:
            return attrs[field]

        return getattr(self.instance, field)

    def validate_geometry(self, geom):
        """ Django will call this method for geometry field validation,
            if the geometry is not valid it will raise a validation error
            example client send "geometry": {"type": "Polygon", "coordinates":
            [[[1.45,43.61],[1.46,43.61],[1.46,43.62],[1.45,43.62],[1.45,43.61]]]}
            GeometryField of DRF converted it to GEOSGeometry : <Point object>.
        """
        try:
            return geo.validate_polygon(geom)
        except geo.InvalidGeometry as error:
            raise serializers.ValidationError(str(error))

    def validate(self, attrs):
        """
        validate the json, if there is a conflict with an existing parcelle
        raise a Conflict exception
        ex {
            "geom": <Polygon object>,
            "code_insee": "31555",
            "prefixe": "000",
            "section": "AB",
            "numero": "42"
            }
        everything is clean regex + validate_geometry
        """
        # if self.instance is not None: dont consider it as a conflict
        exclude = self.instance.pk if self.instance is not None else None

        # On a PATCH, `attrs` holds only the fields the client sent
        geom = self._final_value(attrs, "geom")

        identifier = {
            field: self._final_value(attrs, field) for field in IDENTIFIER_FIELDS
        }
        # search in the database and take the id
        taken = Parcelle.objects.filter(**identifier)
        if exclude is not None:
            # exclude from database in case of put/patch
            taken = taken.exclude(pk=exclude)

        # force django to transform the queryset to a list
        taken = list(taken)
        if taken:
            readable = "-".join(identifier[field] for field in IDENTIFIER_FIELDS)
            raise Conflict(
                "identifiant_deja_pris",
                f"A parcelle already carries the identifier {readable}.",
                taken,
            )

        overlapping = list(geo.overlaps(geom, exclude=exclude))
        if overlapping:
            raise Conflict(
                "chevauchement",
                f"The geometry overlaps {len(overlapping)} existing parcelle(s). "
                "Two parcelles may only share a common border.",
                overlapping,
            )

        return attrs

    def create(self, validated_data):
        """
        create in the database
        validated_data = {
                    "geom": <Polygon object>,
                    "code_insee": "31555",
                    "prefixe": "000",
                    "section": "AB",
                    "numero": "42"
        }
        """
        parcelle = super().create(validated_data)
        return geo.parcelles_with_area().get(pk=parcelle.pk)

    def update(self, instance, validated_data):
        """PUT / PATCH.
        If the geometry has changed, clear the official area so that it is recalculated.
        """
        new_geom = validated_data.get("geom")
        if new_geom is not None and not geo.same_geometry(new_geom, instance.geom):
            instance.surface_m2 = None

        parcelle = super().update(instance, validated_data)
        return geo.parcelles_with_area().get(pk=parcelle.pk)
