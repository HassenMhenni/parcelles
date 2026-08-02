from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """
    Conflict is a DRF exception that returns an HTTP 409 with a structured body.

    The `code` values and the JSON keys below are the published API contract,
    so they keep their original spelling.

    identifier already taken:

    POST /parcelles
    {
    "type": "Feature",
    "geometry": {"type": "Polygon", "coordinates": [[[1.45,43.61],[1.46,43.61],[1.46,43.62],[1.45,43.62],[1.45,43.61]]]},
    "properties": {"code_insee": "31555", "prefixe": "806", "section": "AB", "numero": "139"}
    }
    → 409
    {
    "code": "identifiant_deja_pris",
    "detail": "A parcelle already carries the identifier 31555-806-AB-139.",
    "parcelles_en_conflit": [{"id": 4211, "identifiant": "31555-806-AB-139"}]
    }


    overlap
    PUT /parcelles/7
    # same identifier as before, but geometry moved onto the neighbour's ground
    {"type": "Feature", "geometry": {...polygon overlapping the neighbour...},
    "properties": {"code_insee": "31555", "prefixe": "806", "section": "AB", "numero": "1"}}
    → 409
    {
    "code": "chevauchement",
    "detail": "The geometry overlaps 1 existing parcelle(s). Two parcelles may only share a common border.",
    "parcelles_en_conflit": [{"id": 4212, "identifiant": "31555-806-AB-2"}]
    }

    must be used as raise Conflict(code, detail, parcelles)
    """

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, code, detail, parcelles=()):
        self.detail = {
            "code": code,
            "detail": detail,
            "parcelles_en_conflit": [
                {"id": parcelle.pk, "identifiant": parcelle.identifier}
                for parcelle in parcelles
            ],
        }
