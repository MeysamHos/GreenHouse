from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, ProfileView, LogoutView

urlpatterns = [
    # Registration
    path('register/', RegisterView.as_view(), name='auth-register'),

    # JWT login — POST with {username, password} → returns {access, refresh}
    path('login/', TokenObtainPairView.as_view(), name='auth-login'),

    # Refresh access token — POST with {refresh} → returns new {access}
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),

    # Logout — POST with {refresh} to blacklist the refresh token
    path('logout/', LogoutView.as_view(), name='auth-logout'),

    # Logged-in user's own profile
    path('me/', ProfileView.as_view(), name='auth-me'),
]
