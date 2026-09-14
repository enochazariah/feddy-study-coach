from django.contrib import admin
from django.urls import path, include
from tutoring import views as tutoring_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/tutoring/', include('tutoring.urls')),
    path('api/tutor/', include('tutoring.urls')),
    path('api/active-learning/generate/', tutoring_views.generate_active_learning, name='active_learning_generate'),
    path('api/accounts/', include('accounts.urls')),
    path('api/user/', include('accounts.user_urls')),
]
