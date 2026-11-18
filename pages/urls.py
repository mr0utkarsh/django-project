from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("enquiry/", views.enquiry, name="enquiry"),
    path("signup/", views.signup, name="signup"),
    path("signup/verify/", views.verify_signup_otp, name="verify_signup_otp"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
