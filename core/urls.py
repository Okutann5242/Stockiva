from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('products/', views.product_management, name='products'),
    path('upload-csv/', views.upload_sales_csv, name='upload_csv'),
    path('settings/', views.settings_page, name='settings'),
    path('export-excel/', views.export_sales_excel, name='export_sales_excel'),
    
    # Ürün Güncelleme Modal'ı için en kritik rota!
    path('product/update/<int:product_id>/', views.update_product, name='update_product'),
    path('logout/', views.custom_logout, name='logout'),
    path('api/shopier/webhook/', views.shopier_webhook, name='shopier_webhook'),
    path('integrations/', views.sync_shopier, name='integrations'),
    path('sync-shopier/', views.sync_shopier, name='sync_shopier'),
]