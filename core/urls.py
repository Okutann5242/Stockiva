from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # Ana sayfalar
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('products/', views.product_management, name='products'),
    path('upload-csv/', views.upload_sales_csv, name='upload_csv'),
    path('settings/', views.settings_page, name='settings'),
    path('export-excel/', views.export_sales_excel, name='export_sales_excel'),
    path('integrations/', views.settings_page, name='integrations'),  # Ayarlar sayfasına yönlendirir

    # Ürün işlemleri
    path('product/update/<int:product_id>/', views.update_product, name='update_product'),
    path('product/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('product/add-manual/', views.add_product_manual, name='add_product_manual'),

    # Çıkış (POST only — CSRF güvenliği)
    path('logout/', views.custom_logout, name='logout'),
    path('product/delete/<int:pk>/', views.delete_product, name='delete_product'),

    # Entegrasyonlar
    path('sync-shopier/', views.sync_shopier, name='sync_shopier'),
    path('api/shopier/webhook/', views.shopier_webhook, name='shopier_webhook'),
    path('contact-submit-ajax/', views.contact_submit_ajax, name='contact_submit_ajax'),

    # Ödeme
    path('checkout/', views.checkout, name='checkout'),
    path('iyzico/callback/', views.iyzico_callback, name='iyzico_callback'),

    # Yapay Zeka
    path('ai-analiz/', views.ai_shop_analysis, name='ai_shop_analysis'),
    path('ai-product-analysis/<int:product_id>/', views.ai_product_analysis, name='ai_product_analysis'),

    #Yasal url ler 
    path('about/', TemplateView.as_view(template_name='legal/about.html'), name='about'),
    path('privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='legal/terms.html'), name='terms'),
    path('kvkk/', TemplateView.as_view(template_name='legal/kvkk.html'), name='kvkk'),
    path('membership/', TemplateView.as_view(template_name='legal/membership.html'), name='membership'),
    path('refund/', TemplateView.as_view(template_name='legal/refund.html'), name='refund'),
    path('mss/', TemplateView.as_view(template_name='legal/mss.html'), name='mss'),

    #Hızlı Erişim
    path('ozellikler/', TemplateView.as_view(template_name='fastacces/features.html'), name='features'),
    path('fiyatlandirma/', TemplateView.as_view(template_name='fastacces/prices.html'), name='prices'),
    path('magazabagla/', TemplateView.as_view(template_name='fastacces/integrations.html'), name='integrations'),
    
]
