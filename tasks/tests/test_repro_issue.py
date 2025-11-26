from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from tasks.views import add_list_with_users
from django.contrib.messages.middleware import MessageMiddleware

User = get_user_model()

class ReproIssueTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.user.is_staff = True
        self.user.save()

    def test_add_list_view_with_lazy_user(self):
        request = self.factory.get('/todo/add_list/')
        
        # Simulate middleware
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        
        auth_middleware = AuthenticationMiddleware(lambda r: None)
        auth_middleware.process_request(request)
        
        # Force login in session
        request.session['_auth_user_id'] = self.user.pk
        request.session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        request.session['_auth_user_hash'] = self.user.get_session_auth_hash()
        request.session.save()
        
        # Re-run auth middleware to get SimpleLazyObject
        auth_middleware.process_request(request)
        
        msg_middleware = MessageMiddleware(lambda r: None)
        msg_middleware.process_request(request)

        print(f"User type: {type(request.user)}")
        
        try:
            response = add_list_with_users(request)
            print(f"Response status: {response.status_code}")
        except Exception as e:
            print(f"Caught exception: {e}")
            import traceback
            traceback.print_exc()
