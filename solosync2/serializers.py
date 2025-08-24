# solosync2/serializers.py
from rest_framework import serializers
# CORRECTED IMPORT: Drill is still in scheduling...
from scheduling.models import Drill 
# ...but Routine and RoutineDrill are now in this app's models.
from .models import SoloSessionLog, Routine, RoutineDrill 

class DrillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drill
        fields = ['id', 'name', 'description']

class RoutineDrillSerializer(serializers.ModelSerializer):
    drill = DrillSerializer(read_only=True)

    class Meta:
        model = RoutineDrill
        fields = ['order', 'duration_minutes', 'rest_duration_seconds', 'drill']

class RoutineSerializer(serializers.ModelSerializer):
    drills = RoutineDrillSerializer(source='drills_in_routine', many=True, read_only=True)

    class Meta:
        model = Routine
        fields = ['id', 'name', 'description', 'drills']

class SoloSessionLogSerializer(serializers.ModelSerializer):
    player = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = SoloSessionLog
        fields = [
            'id', 'player', 'routine', 'completed_at', 'duration_minutes', 
            'exertion_rating', 'focus_rating', 'notes'
        ]
        read_only_fields = ['id', 'completed_at', 'player']

class SoloSessionLogSerializer(serializers.ModelSerializer):
    player = serializers.StringRelatedField(read_only=True)
    # ADD THIS LINE to show the routine's name in the API list view
    routine = serializers.StringRelatedField(read_only=True) 

    class Meta:
        model = SoloSessionLog
        fields = [
            'id', 'player', 'routine', 'completed_at', 'duration_minutes', 
            'exertion_rating', 'focus_rating', 'notes'
        ]
        # When creating a log, we still need to pass the routine ID
        # This setup makes the `routine` field behave differently for reading vs. writing
        extra_kwargs = {
            'routine': {'write_only': True, 'required': True}
        }