from django import forms
from django.contrib import admin
from django.contrib.gis import admin as gis_admin

from . import geo
from .models import Parcelle
from .serializers import IDENTIFIER_FIELDS, IDENTIFIER_VALIDATORS

DEFAULT_CENTRE = {"default_lon": 1.4442, "default_lat": 43.6047, "default_zoom": 15}

# listed conflicts is the number of overlapping parcelles to list in the error message
LISTED_CONFLICTS = 5


class SectionField(forms.CharField):
    """
     A custom field that uppercases the value used for the section of a parcelle.
    """

    def to_python(self, value):
        value = super().to_python(value)
        return value.upper() if value else value


class ParcelleForm(forms.ModelForm):
    """
    Form class for creation and edit
    """

    class Meta:
        model = Parcelle
        fields = (*IDENTIFIER_FIELDS, "geom")
        field_classes = {"section": SectionField}
        widgets = {
            field: forms.TextInput(attrs={"size": 8}) for field in IDENTIFIER_FIELDS
        }

    def __init__(self, *args, **kwargs):
        """
        add the regex validators for the four fields of the identifier
        (code_insee, prefixe, section, numero)
        """
        super().__init__(*args, **kwargs)
        for field, validator in IDENTIFIER_VALIDATORS.items():
            self.fields[field].validators.append(validator)

    def clean_geom(self):
        """
        Validate the geometry field.
        """
        # cleaned_data is a dict with the cleaned values of the form fields,
        # after validation
        geom = self.cleaned_data["geom"]
        try:
            return geo.validate_polygon(geom)
        except geo.InvalidGeometry as error:
            raise forms.ValidationError(str(error)) from error

    def clean(self):
        """
        Check that the geometry does not overlap with existing parcelles.
        """
        cleaned = super().clean()

        geom = cleaned.get("geom")
        if geom is None:
            return cleaned

        overlapping = list(geo.overlaps(geom, exclude=self.instance.pk))
        if overlapping:
            raise forms.ValidationError(
                {"geom": [self._overlap_message(overlapping)]}
            )

        return cleaned

    @staticmethod
    def _overlap_message(overlapping):
        listed = ", ".join(parcelle.identifier for parcelle in overlapping[:LISTED_CONFLICTS])
        remaining = len(overlapping) - LISTED_CONFLICTS
        if remaining > 0:
            listed += f" and {remaining} other(s)"

        return (
            f"The geometry overlaps {len(overlapping)} existing parcelle(s): "
            f"{listed}. Two parcelles may only share a common border."
        )


# registration of the Parcelle model in Django admin
@admin.register(Parcelle)
class ParcelleAdmin(gis_admin.GISModelAdmin):
    """The Parcelle model in the admin interface"""

    form = ParcelleForm
    gis_widget_kwargs = {"attrs": DEFAULT_CENTRE}

    list_display = ("identifier", "section", "numero", "area", "updated_on")
    list_filter = ("code_insee", "prefixe", "section")
    search_fields = IDENTIFIER_FIELDS
    list_per_page = 50
    ordering = ("id",)

    readonly_fields = ("area", "bbox", "geojson", "created_on", "updated_on")

    fieldsets = (
        ("Cadastral identifier", {"fields": (IDENTIFIER_FIELDS,)}),
        (
            "Geometry",
            {
                "fields": ("geom", "area", "bbox"),
                "description": (
                    "The polygon is in WGS84 (EPSG:4326). The bounding box is "
                    "recomputed on save; redrawing the geometry clears the "
                    "official area, just like on the API."
                ),
            },
        ),
        ("GeoJSON", {"fields": ("geojson",), "classes": ("collapse",)}),
        ("Tracking", {"fields": ("created_on", "updated_on"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        """
        display the parcelles with the area calculated
        """
        return geo.parcelles_with_area()

    def get_search_results(self, request, queryset, search_term):
        """Make a pasted identifier (`31555-806-AB-139`) find its parcelle, by
        splitting it back onto its four columns; anything else falls through to
        the default search.
        """
        parts = search_term.strip().split("-")
        if len(parts) == len(IDENTIFIER_FIELDS) and all(parts):
            identifier = {
                field: part.strip().upper()
                for field, part in zip(IDENTIFIER_FIELDS, parts)
            }
            return queryset.filter(**identifier), False

        return super().get_search_results(request, queryset, search_term)

    def save_model(self, request, obj, form, change):
        """
        If the geometry has changed, clear the official area so that it is recalculated
        """
        if change and obj.surface_m2 is not None:
            previous = Parcelle.objects.get(pk=obj.pk).geom
            if not geo.same_geometry(obj.geom, previous):
                obj.surface_m2 = None

        # `Parcelle.save()` fills the bounding box in from the geometry.
        super().save_model(request, obj, form, change)

    # ----------------------------------------------------------- read-only

    @admin.display(description="area (m²)")
    def area(self, parcelle):
        """
        The area in square metres, as stored or computed. Rounded to 1 decimal
        """
        if parcelle.surface_m2 is not None:
            return f"{parcelle.surface_m2:.1f}"

        computed = getattr(parcelle, "computed_area", None)
        if computed is None:  # add form: nothing computed yet
            return "—"

        return f"{computed.sq_m:.1f}"

    @admin.display(description="bounding box")
    def bbox(self, parcelle):
        """min_lon, min_lat, max_lon, max_lat, as stored."""
        if parcelle.pk is None:
            return "—"

        return ", ".join(f"{coordinate:.6f}" for coordinate in parcelle.bbox)

    @admin.display(description="created on")
    def created_on(self, parcelle):
        return parcelle.created_at

    @admin.display(description="updated on", ordering="updated_at")
    def updated_on(self, parcelle):
        return parcelle.updated_at

    @admin.display(description="GeoJSON geometry")
    def geojson(self, parcelle):
        """The geometry as the API would return it, ready to be replayed."""
        if parcelle.geom is None:
            return "—"

        return parcelle.geom.geojson


admin.site.site_header = "Cadastral parcelles"
admin.site.site_title = "Cadastral parcelles"
admin.site.index_title = "Administration"
