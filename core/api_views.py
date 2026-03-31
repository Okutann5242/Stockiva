from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Product, Sale # Kendi modellerin
import json

@api_view(['POST'])
@permission_classes([AllowAny]) # Shopier'ın erişebilmesi için şifresiz olmalı
def shopier_webhook(request):
    # 1. Shopier'dan gelen veriyi al
    data = request.data 
    
    # Shopier'dan gelen örnek veri: {'platform_order_id': '123', 'product_name': 'Kulaklık', 'price': 500}
    product_name = data.get('product_name')
    quantity = int(data.get('quantity', 1))
    price = float(data.get('total_amount'))

    # 2. Veritabanında ürünü bul ve stoğu düş
    try:
        product = Product.objects.get(name__icontains=product_name)
        product.stock_quantity -= quantity
        product.save()

        # 3. Satış tablosuna ekle (Dashboard'da görünmesi için)
        Sale.objects.create(
            product=product,
            quantity=quantity,
            price=price
        )
        return Response({"status": "success"}, status=200)
    except Product.DoesNotExist:
        return Response({"status": "error", "message": "Ürün bulunamadı"}, status=404)