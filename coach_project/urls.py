# coach_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from scheduling.views import homepage

#// solosync imports

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # THIS IS THE CRUCIAL CHANGE:
    # We now point /accounts/ to our own app's urls.py file.
    path('accounts/', include('accounts.urls')),

    #password reset
    path('accounts/', include('django.contrib.auth.urls')),

    # --- The rest of your app includes ---
    path('', homepage, name='homepage'),
    path('players/', include('players.urls')),
    path('schedule/', include('scheduling.urls')),
    path('live-session/', include('live_session.urls')),
    path('assessments/', include('assessments.urls')),
    path('finance/', include('finance.urls')),

    #// solosync2 urls
    path('api/solosync2/', include('solosync2.urls')),

    #// ADD THESE TWO URLS for getting and refreshing tokens
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),


    


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
