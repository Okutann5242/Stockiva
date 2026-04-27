from django import forms
from django.contrib.auth.models import User

class UploadCSVForm(forms.Form):
    file = forms.FileField()

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class ProfileUpdateForm(forms.ModelForm):
    phone = forms.CharField(max_length=15, required=False)
    critical_stock_alert = forms.BooleanField(required=False) # E-posta uyarısı için
    
    class Meta:
        model = Profile # Senin Profil modelin
        fields = ['phone', 'critical_stock_alert']