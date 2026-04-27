from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ŞİFRE SIFIRLAMA (PASSWORD RESET)
    path('sifre-yenile/', views.MyPasswordResetView.as_view(), name='password_reset'), # Name standart kalsın
    path('sifre-yenile/bitti/', views.MyPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('yenile/<uidb64>/<token>/', views.MyPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('yenile/done/', views.MyPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # AKTİVASYON VE PROFİL
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('verification-sent/', views.verification_sent, name='verification_sent'),
    path('resend-activation/', views.resend_activation, name='resend_activation'),
    path('profile/', views.profile_view, name='profile'),
]