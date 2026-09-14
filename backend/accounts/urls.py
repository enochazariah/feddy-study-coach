from django.urls import path

from . import views

urlpatterns = [
    path("google", views.google_sign_in, name="google-sign-in"),
    path("demo-login/", views.demo_login, name="demo-login"),
    path("me", views.me, name="account-me"),
]
