from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-Posta Adresi")

    class Meta:
        model = User
        fields = ['username', 'email'] # password alanlarını Django kendi ekler

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control bg-light', 'placeholder': 'Kullanıcı Adı'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control bg-light', 'placeholder': 'Şifre'}))