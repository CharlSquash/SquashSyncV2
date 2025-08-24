# solosync2/serializers.py
from rest_framework import serializers
from scheduling.models import Drill 
from .models import SoloSessionLog, Routine, RoutineDrill 

class DrillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drill
        fields = ['id', 'name', 'description', 'youtube_link']

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
    routine = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = SoloSessionLog
        fields = [
            'id', 'player', 'routine', 'completed_at', 'difficulty_rating', 
            'likelihood_rating', 'notes'
        ]
        extra_kwargs = {
            'routine': {'write_only': True, 'required': True}
        }