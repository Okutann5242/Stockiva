from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site

from .forms import RegisterForm
from .tokens import account_activation_token
from django.urls import reverse_lazy

User = get_user_model()
print("SAYFA YENİLENDİ")
@login_required
def profile_view(request):
    profile = request.user.profile
    if request.method == "POST":
        request.user.first_name = request.POST.get("first_name")
        request.user.last_name = request.POST.get("last_name")
        request.user.email = request.POST.get("email")
        profile.phone = request.POST.get("phone")
        
        request.user.save()
        profile.save()
        messages.success(request, "Profil güncellendi")
        return redirect("profile")
    return render(request, "accounts/profile.html", {"profile": profile})

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False # Aktivasyon bekliyor
            user.save()

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = request.build_absolute_uri(f"/accounts/activate/{uid}/{token}/")

            subject = "Hesabını Aktifleştir"
            message = f"Merhaba {user.username},\n\nHesabını aktifleştirmek için linke tıkla:\n\n{activation_link}\n\nStockiva"
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
            return redirect('verification_sent')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'accounts/activation_invalid.html')

def verification_sent(request):
    return render(request, 'accounts/verification_sent.html')

def resend_activation(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                messages.info(request, "Hesap zaten aktif.")
                return redirect("login")

            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            
            message = f"Hesabını tekrar aktifleştir:\n\nhttp://{current_site.domain}/accounts/activate/{uid}/{token}/"

            send_mail("Aktivasyon Linki", message, settings.DEFAULT_FROM_EMAIL, [user.email])
            messages.success(request, "Mail tekrar gönderildi.")
            return redirect("verification_sent")
        except User.DoesNotExist:
            messages.error(request, "Kullanıcı bulunamadı.")
    return render(request, "accounts/resend.html")


from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView

# accounts/views.py içindeki şifre sınıfları

class MyPasswordResetView(PasswordResetView):
    template_name = 'accounts/sifre_yenile.html'
    email_template_name = 'accounts/sifre_yenile_email.html'
    success_url = reverse_lazy('password_reset_done') # urls.py'deki isme gider

class MyPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/sifre_yenile_bitti.html'

class MyPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/sifre_yenile_onayla.html'
    success_url = reverse_lazy('password_reset_complete')

class MyPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/sifre_yenile_complete.html'