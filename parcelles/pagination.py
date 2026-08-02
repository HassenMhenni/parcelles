from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class FeatureCollectionPagination(PageNumberPagination):
    """
    Pagination class
    must be used in the settings.py
    """
    page_size = 200
    page_size_query_param = "page_size"
    max_page_size = 1000

    def get_paginated_response(self, data):
        """called automaticaly by the serializer after every GET
        """
        # RFC 7946 for feature collections
        # count is not mendatory in RFC 7946: "Foreign members MAY be present,
        # parsers MUST ignore them"
        return Response(
            {
                "type": "FeatureCollection",
                "count": self.page.paginator.count,
                "features": data,
            }
        )
