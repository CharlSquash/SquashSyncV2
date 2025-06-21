# coach_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from scheduling.views import homepage

urlpatterns = [
    path('admin/', admin.site.urls),

    # THIS IS THE CRUCIAL CHANGE:
    # We now point /accounts/ to our own app's urls.py file.
    path('accounts/', include('accounts.urls')),

    # --- The rest of your app includes ---
    path('', homepage, name='homepage'),
    path('players/', include('players.urls')),
    path('schedule/', include('scheduling.urls')),
    path('live-session/', include('live_session.urls')),
    path('assessments/', include('assessments.urls')),
    path('finance/', include('finance.urls')),

    


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)