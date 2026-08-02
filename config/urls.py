"""Routing: the JSON API at the root, the back-office under /admin.

The two entry points share the same rules — see parcelles/admin.py — but not the
same audience: /parcelles is public and unauthenticated, /admin/ requires a
staff account.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("parcelles.urls")),
]
