"""
python manage.py init_db            # first install
python manage.py init_db --reset    # start again from an empty table

"""

import csv

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from ...models import Parcelle

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = (
        "Creates the PostGIS extension, the `parcelle` table and its indexes "
        "(db/schema.sql), then loads the parcelles from the CSV."
    )

    def add_arguments(self, parser):
        """Command-line options, parsed by argparse."""
        parser.add_argument(
            "--reset",
            action="store_true",
            help="drops the existing `parcelle` table before recreating it.",
        )
        parser.add_argument(
            "--csv",
            default=str(settings.PARCELLES_CSV),
            help=f"path of the CSV to load (default: {settings.PARCELLES_CSV}).",
        )

    def handle(self, *args, **options):
        """Entry point: Django calls this with the parsed options."""
        if self._table_exists():
            if not options["reset"]:
                raise CommandError(
                    "The `parcelle` table already exists. Run again with --reset "
                    "to recreate it (the current data will be lost)."
                )
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE parcelle CASCADE")
            self.stdout.write("Table `parcelle` dropped (--reset).")

        with connection.cursor() as cursor:
            cursor.execute(settings.SCHEMA_SQL.read_text(encoding="utf-8"))
        self.stdout.write(f"Schema applied from {settings.SCHEMA_SQL}.")

        self._load(options["csv"])

    def _table_exists(self):
        """True if the `parcelle` table is already there.

        `to_regclass` returns NULL instead of raising when the table is unknown,
        which makes it the cheapest existence test in PostgreSQL.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('parcelle') IS NOT NULL")
            return cursor.fetchone()[0]

    def _load(self, csv_path):
        try:

            file = open(csv_path, newline="", encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"Unreadable CSV ({csv_path}): {exc}") from exc

        with file, transaction.atomic():
            parcelles = [self._parcelle(row) for row in csv.DictReader(file)]
            Parcelle.objects.bulk_create(parcelles, batch_size=BATCH_SIZE)

            with connection.cursor() as cursor:
                cursor.execute("ANALYZE parcelle")

        self.stdout.write(
            self.style.SUCCESS(f"{len(parcelles)} parcelles loaded from {csv_path}.")
        )

    @staticmethod
    def _parcelle(row):

        return Parcelle(
            code_insee=row["code_insee"],
            prefixe=row["prefixe"],
            section=row["section"],
            numero=row["numero"],
            geom=GEOSGeometry(row["geojson"], srid=4326),
            min_lon=float(row["min_lon"]),
            min_lat=float(row["min_lat"]),
            max_lon=float(row["max_lon"]),
            max_lat=float(row["max_lat"]),
            surface_m2=float(row["surface_m2"]) if row["surface_m2"] else None,
        )
