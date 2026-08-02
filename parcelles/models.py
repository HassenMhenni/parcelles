
# `django.contrib.gis.db.models` exposes the same fields as
# `django.db.models`, plus the geographic ones (PolygonField, PointField...).
# https://docs.djangoproject.com/en/5.1/ref/contrib/gis/model-api/
from django.contrib.gis.db import models


class Parcelle(models.Model):
    """A cadastral parcelle: a business identifier and a polygon.

        Parcelle.objects.create(
            code_insee="31555", prefixe="000", section="AB", numero="42",
            geom="POLYGON((1.44 43.60, 1.441 43.60, 1.441 43.601, 1.44 43.601, 1.44 43.60))",
        )

    The bounding box is filled in by `save()`, the timestamps by Django.

    The field names below are the column names of the `parcelle` table
    (db/schema.sql) and the property names of the GeoJSON API, so they keep
    their cadastral spelling.
    """

    # BigAutoField (64 bits) rather than AutoField (32 bits): the French
    # cadastre holds around a hundred million parcelles, so we stay on the safe
    # side. https://docs.djangoproject.com/en/5.1/ref/models/fields/#bigautofield
    id = models.BigAutoField(primary_key=True)

    # The quadruplet uniquely identifies a parcelle (see the assignment). Stored
    # as text: the prefix and the number may carry meaningful leading zeros.
    code_insee = models.TextField()
    prefixe = models.TextField()
    section = models.TextField()
    numero = models.TextField()

    # SRID 4326 = WGS84, longitude/latitude in degrees — the GeoJSON system.
    # A sequence of GPS points forming a closed polygon, e.g.
    # ((1.44 43.60, 1.441 43.60, 1.441 43.601, 1.44 43.601, 1.44 43.60)).
    geom = models.PolygonField(srid=4326)

    min_lon = models.FloatField()
    min_lat = models.FloatField()
    max_lon = models.FloatField()
    max_lat = models.FloatField()

    # area is then computed during POST (see geo.AREA_M2).
    surface_m2 = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # refreshed on every save()

    class Meta:
        # How Django handles the table: `makemigrations` + `migrate` will not
        # create it, since db/schema.sql already does.
        managed = False
        # Without db_table Django would pick a name of its own (parcelles_parcelle).
        db_table = "parcelle"
        verbose_name = "parcelle"
        verbose_name_plural = "parcelles"
        constraints = [
            # "The quadruplet (code_insee, prefixe, section, numero) uniquely
            # identifies a parcelle" — from the assignment.
            # The name matches the constraint declared in db/schema.sql.
            models.UniqueConstraint(
                fields=["code_insee", "prefixe", "section", "numero"],
                name="parcelle_identifiant_unique",
            )
        ]

    def __str__(self):
        return self.identifier

    # @property means it is accessed like an attribute: `p.identifier`,
    # not `p.identifier()`.
    @property
    def identifier(self):
        return f"{self.code_insee}-{self.prefixe}-{self.section}-{self.numero}"

    @property
    def bbox(self):
        """(min_lon, min_lat, max_lon, max_lat), as stored."""
        return [self.min_lon, self.min_lat, self.max_lon, self.max_lat]

    def save(self, *args, **kwargs):
        """Recompute the bounding box on every save.
        """
        if self.geom is not None:
            # `GeoGeometry.extent` comes from GeoDjango: the rectangle enclosing the polygon.
            self.min_lon, self.min_lat, self.max_lon, self.max_lat = self.geom.extent

            fields = kwargs.get("update_fields")
            if fields is not None:
                kwargs["update_fields"] = {
                    *fields,
                    "min_lon",
                    "min_lat",
                    "max_lon",
                    "max_lat",
                }

        super().save(*args, **kwargs)
