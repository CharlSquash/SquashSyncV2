# scheduling/serializers.py
from rest_framework import serializers
from .models import Drill, Routine, RoutineDrill

class DrillSerializer(serializers.ModelSerializer):
    """
    Serializer for the Drill model, providing basic details.
    """
    class Meta:
        model = Drill
        # FIX: Add 'youtube_link' to this list
        fields = ['id', 'name', 'description', 'duration_minutes_default', 'youtube_link']

class RoutineDrillSerializer(serializers.ModelSerializer):
    """
    Serializer for the ordered drills within a routine.
    It includes the full details of the drill itself.
    """
    drill = DrillSerializer(read_only=True)

    class Meta:
        model = RoutineDrill
        # This now includes the specific duration for the drill within this routine
        fields = ['order', 'drill', 'duration_minutes']

class RoutineSerializer(serializers.ModelSerializer):
    """
    Serializer for the main Routine model. It includes a nested list
    of all its drills, correctly ordered.
    """
    # This uses the RoutineDrillSerializer to represent the ordered drills
    drills = RoutineDrillSerializer(source='routinedrill_set', many=True, read_only=True)

    class Meta:
        model = Routine
        fields = ['id', 'name', 'description', 'drills']