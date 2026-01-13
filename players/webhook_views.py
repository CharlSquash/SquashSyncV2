import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .models import Player, GenderChoices

class GravityFormWebhookView(APIView):
    """
    Endpoint to receive JSON webhook from Gravity Forms (WordPress).
    Verifies secret token in headers.
    Checks for duplicates before crating a new Player.
    """
    permission_classes = []  # Allow unauthenticated access (we handle token check manually)

    def post(self, request, *args, **kwargs):
        # 1. Authentication
        token = request.headers.get('X-SquashSync-Token')
        secret_key = os.environ.get('GRAVITY_FORMS_SECRET_KEY')

        if not secret_key or token != secret_key:
            return Response(
                {"detail": "Invalid or missing token."},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data

        # 2. Field Parsing & Logic

        # Grade: Convert string to int, verify choice.
        raw_grade = data.get('grade')
        grade_value = None
        if raw_grade is not None:
            try:
                # Handle cases like "9" or 9
                g_int = int(raw_grade)
                if g_int in Player.GradeLevel.values:
                    grade_value = g_int
            except (ValueError, TypeError):
                pass
        
        # Gender: Default to UNSPECIFIED
        # (JSON does not send gender currently, per requirements)
        gender_value = GenderChoices.UNSPECIFIED

        # Extract other fields
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        parent_email = data.get('parent_email', '').strip()

        # 3. Duplicate Check
        # Check if a Player exists with the same first_name, last_name, and parent_email
        if first_name and last_name:
            # We filter by parent_email only if it's provided, or strict match if requirement implies strict tuple check
            # Requirement: "Check if a Player exists with the same first_name, last_name, and parent_email"
            # Assuming if email matches (empty or not)
            
            # Construct dictionary for filter to handle potential empty email matching behavior if desired,
            # but usually unique verification implies active fields. 
            # Let's check strict equality on these three str fields.
            
            duplicate_qs = Player.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                parent_email__iexact=parent_email
            )

            if duplicate_qs.exists():
                print(f"Duplicate registration attempt: {first_name} {last_name} ({parent_email})")
                return Response({
                    "status": "skipped",
                    "message": "Duplicate"
                }, status=status.HTTP_200_OK)

        # 4. Creation
        try:
            player = Player.objects.create(
                first_name=first_name,
                last_name=last_name,
                parent_email=parent_email if parent_email else None,
                parent_contact_number=data.get('parent_contact_number', ''),
                contact_number=data.get('contact_number', ''), # Player cell
                school=data.get('school', ''),
                grade=grade_value,
                gender=gender_value,
                health_information=data.get('health_information', ''),
                medical_aid_number=data.get('medical_aid_number', ''),
                guardian_2_name=data.get('guardian_2_name', ''),
                guardian_2_contact_number=data.get('guardian_2_contact_number', ''),
                guardian_2_email=data.get('guardian_2_email') or None, # Use None if empty string
                notes=data.get('notes', '')
            )
        except Exception as e:
            # Catch DB errors etc.
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Response
        return Response({
            "status": "success",
            "player_id": player.pk
        }, status=status.HTTP_200_OK)
