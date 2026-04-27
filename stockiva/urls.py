from django.contrib import admin
from django.urls import path, include 
from two_factor.urls import urlpatterns as tf_urls

urlpatterns = [
    path('', include(tf_urls)),# 2FA yolları
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')), # Bütün hesap işlemleri burada
    path('', include('core.urls')),              # Dashboard vb.
                     
]