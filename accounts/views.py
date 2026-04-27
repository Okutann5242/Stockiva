import logging

from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.contrib.sites.shortcuts import get_current_site

from .forms import RegisterForm
from .tokens import account_activation_token
from .forms import RegisterForm, UserUpdateForm, ProfileUpdateForm # İçe aktarmalara ekle
logger = logging.getLogger('accounts')
User = get_user_model()


# ==============================================================================
# 👤 PROFİL
# ==============================================================================



@login_required
def profile_view(request):
    """Kullanıcı profil sayfası."""
    profile = request.user.profile
    
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, '✅ Profil güncellendi.')
            return redirect('profile')
        else:
            messages.error(request, 'Lütfen formdaki hataları düzeltin.')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)
        
    return render(request, 'accounts/profile.html', {
        'u_form': u_form, 
        'p_form': p_form,
        'profile': profile
    })


# ==============================================================================
# 📝 KAYIT VE AKTİVASYON
# ==============================================================================

def register_view(request):
    """Yeni kullanıcı kaydı. Kayıt sonrası e-posta aktivasyonu gönderir."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Aktivasyon bekliyor
            user.save()

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            domain = get_current_site(request).domain

            html_message = render_to_string('accounts/activation_email.html', {
                'user': user,
                'domain': domain,
                'uid': uid,
                'token': token,
            })

            try:
                send_mail(
                    subject="Stockiva'ya Hoş Geldin! 🚀",
                    message=f'Hesabınızı aktifleştirin: http://{domain}/accounts/activate/{uid}/{token}/',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f'Aktivasyon maili gönderildi: {user.email}')
            except Exception as e:
                logger.error(f'Aktivasyon maili gönderilemedi ({user.email}): {e}')
                # Mail gönderilemese bile kullanıcıyı kaydet, resend sayfasına yönlendir
                messages.warning(request, '⚠️ Aktivasyon maili gönderilemedi. Tekrar gönder butonunu kullanabilirsin.')

            return redirect('verification_sent')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def activate(request, uidb64, token):
    """
    E-posta aktivasyon linki işleyicisi.
    DÜZELTME: login() çağrısında backend belirtildi (Axes + 2FA uyumu).
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        # DÜZELTME: backend belirtildi — Axes'in backend'iyle çakışmayı önler
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, '🎉 Hesabın aktif! Hoş geldin.')
        return redirect('dashboard')

    logger.warning(f'Geçersiz aktivasyon token: uidb64={uidb64}')
    return render(request, 'accounts/activation_invalid.html')


def verification_sent(request):
    """Aktivasyon maili gönderildi bilgi sayfası."""
    return render(request, 'accounts/verification_sent.html')


def resend_activation(request):
    """Aktivasyon mailini yeniden gönderir."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                messages.info(request, 'Bu hesap zaten aktif. Giriş yapabilirsin.')
                return redirect('two_factor:login')

            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            domain = current_site.domain

            html_message = render_to_string('accounts/activation_email.html', {
                'user': user,
                'domain': domain,
                'uid': uid,
                'token': token,
            })

            send_mail(
                subject='Yeni Aktivasyon Linki — Stockiva 🚀',
                message=f'Hesabınızı aktifleştirin: http://{domain}/accounts/activate/{uid}/{token}/',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            messages.success(request, '✅ Aktivasyon maili tekrar gönderildi. Gelen kutunu kontrol et.')
            return redirect('verification_sent')

        except User.DoesNotExist:
            # Güvenlik: kullanıcı yoksa da aynı mesajı ver (kullanıcı tespitini engelle)
            messages.error(request, 'Bu e-posta adresiyle kayıtlı kullanıcı bulunamadı.')

    return render(request, 'accounts/resend.html')


# ==============================================================================
# 🔑 ŞİFRE SIFIRLAMA
# ==============================================================================

class MyPasswordResetView(PasswordResetView):
    template_name = 'accounts/sifre_yenile.html'
    email_template_name = 'accounts/sifre_yenile_email.html'
    html_email_template_name = 'accounts/sifre_yenile_email.html'
    success_url = reverse_lazy('password_reset_done')


class MyPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/sifre_yenile_bitti.html'


class MyPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/sifre_yenile_onayla.html'
    success_url = reverse_lazy('password_reset_complete')


class MyPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/sifre_yenile_complete.html'
