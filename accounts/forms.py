from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Profile


class RegisterForm(UserCreationForm):
    """Yeni kullanıcı kayıt formu."""
    email = forms.EmailField(
        required=True,
        label='E-Posta Adresi',
        widget=forms.EmailInput(attrs={'placeholder': 'ornek@mail.com'})
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        # password1, password2 UserCreationForm tarafından otomatik eklenir


class LoginForm(AuthenticationForm):
    """Özelleştirilmiş giriş formu."""
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kullanıcı Adı'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Şifre'})
    )


class UserUpdateForm(forms.ModelForm):
    """Kullanıcı temel bilgi güncelleme formu."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class ProfileUpdateForm(forms.ModelForm):
    """ 
    Profil güncelleme formu.
    DÜZELTME: Önceki formda 'phone' yazıyordu ama model alanı 'phone_number'.
    'critical_stock_alert' modelde yoktu, 'email_notifications' ile değiştirildi.
    """
    class Meta:
        model = Profile
        fields = ['phone_number', 'email_notifications', 'monthly_revenue_goal', 'shopier_api_key']
        labels = {
            'phone_number': 'Telefon Numarası',
            'email_notifications': 'E-posta Bildirimleri',
            'monthly_revenue_goal': 'Aylık Ciro Hedefi (₺)',
            'shopier_api_key': 'Shopier API Anahtarı',
        }
        widgets = {
            'phone_number': forms.TextInput(attrs={'placeholder': '+905xxxxxxxxx'}),
            'monthly_revenue_goal': forms.NumberInput(attrs={'min': '0', 'step': '1000'}),
        }
