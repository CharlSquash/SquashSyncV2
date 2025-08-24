# solosync2/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoutineViewSet, SoloSessionLogViewSet

router = DefaultRouter()
router.register(r'routines', RoutineViewSet)
router.register(r'logs', SoloSessionLogViewSet, basename='solosessionlog')

urlpatterns = [
    path('', include(router.urls)),
]