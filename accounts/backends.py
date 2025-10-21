# accounts/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

UserModel = get_user_model()

class EmailOrUsernameModelBackend(ModelBackend):
    """
    This is a custom authentication backend.
    It allows users to log in with either their username or their email address.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        # The Q object allows for complex queries, in this case, an OR condition.
        # We check for a case-insensitive match on either the username or the email field.
        try:
            # Note: We use iexact for case-insensitive matching
            user = UserModel.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between a non-existent and an existing user.
            UserModel().set_password(password)
            return
        except UserModel.MultipleObjectsReturned:
            # This can happen if two users have the same email address (case-insensitively).
            # We prioritize the exact username match first.
            try:
                user = UserModel.objects.get(username__iexact=username)
            except UserModel.DoesNotExist:
                # If that still fails, we can't be sure which user to authenticate.
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
