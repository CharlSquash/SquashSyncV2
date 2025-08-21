# scheduling/api_views.py
from rest_framework import viewsets, permissions
from .models import Routine
from .serializers import RoutineSerializer

class RoutineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A read-only API endpoint that allows players to view active routines.
    """
    queryset = Routine.objects.filter(is_active=True).prefetch_related('routinedrill_set__drill')
    serializer_class = RoutineSerializer
    permission_classes = [permissions.IsAuthenticated] # Only logged-in users can see routines
