import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Parcelle",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code_insee", models.TextField()),
                ("prefixe", models.TextField()),
                ("section", models.TextField()),
                ("numero", models.TextField()),
                ("geom", django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ("min_lon", models.FloatField()),
                ("min_lat", models.FloatField()),
                ("max_lon", models.FloatField()),
                ("max_lat", models.FloatField()),
                ("surface_m2", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "parcelle",
                "verbose_name_plural": "parcelles",
                "db_table": "parcelle",
                "managed": False,
            },
        ),
    ]
