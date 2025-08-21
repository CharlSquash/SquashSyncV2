# players/serializers.py
from rest_framework import serializers
from .models import SoloPracticeLog

class SoloPracticeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoloPracticeLog
        fields = ['id', 'date', 'duration_minutes', 'notes']
        read_only_fields = ['id', 'date']