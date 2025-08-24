# solosync2/views.py
from rest_framework import viewsets, permissions
from rest_framework.permissions import IsAuthenticated
# CORRECTED IMPORT: We now import Routine from this app's models
from .models import Routine, SoloSessionLog 
from players.models import Player
# CORRECTED IMPORT: We now import the serializers from this app
from .serializers import RoutineSerializer, SoloSessionLogSerializer

class IsPlayer(permissions.BasePermission):
    """
    Custom permission to only allow users with a player profile.
    """
    def has_permission(self, request, view):
        return hasattr(request.user, 'player_profile')

class RoutineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A read-only API endpoint for players to view available solo routines.
    """
    queryset = Routine.objects.all()
    serializer_class = RoutineSerializer
    permission_classes = [IsAuthenticated, IsPlayer]

class SoloSessionLogViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows players to create and view their solo session logs.
    """
    serializer_class = SoloSessionLogSerializer
    permission_classes = [IsAuthenticated, IsPlayer]

    def get_queryset(self):
        """
        This view should return a list of all the solo session logs
        for the currently authenticated user's player profile.
        """
        player = self.request.user.player_profile
        return SoloSessionLog.objects.filter(player=player)

    def perform_create(self, serializer):
        """
        Associate the log with the currently logged-in player.
        """
        player = self.request.user.player_profile
        serializer.save(player=player)