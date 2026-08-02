from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("parcelles", views.ParcelleListCreateView.as_view(), name="parcelle-list"),
    path("parcelles/<int:pk>", views.ParcelleDetailView.as_view(), name="parcelle-detail"),
    path(
        "parcelles/<int:pk>/voisines",
        views.ParcelleNeighboursView.as_view(),
        name="parcelle-neighbours",
    ),
]
