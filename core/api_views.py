from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Product, Sale

@api_view(['POST'])
@permission_classes([AllowAny])
def shopier_webhook(request):
    # Shopier veriyi bazen 'data' değil direkt POST içinden gönderir
    # DRF kullandığın için request.data en doğrusu
    data = request.data 
    
    # Shopier'den gelen gerçek parametre isimleri genelde şöyledir:
    # 'platform_order_id', 'product_name', 'total_order_value'
    product_name = data.get('product_name')
    # Miktar verisi gelmezse varsayılan 1 alalım
    quantity = int(data.get('quantity', 1)) 
    # Tutar verisi Shopier'de 'total_order_value' veya 'price' olabilir
    price = float(data.get('total_order_value', 0))

    try:
        # Ürünü isminden yakala (Küçük-Büyük harf duyarsız)
        product = Product.objects.get(name__icontains=product_name)
        
        # Stok Düşürme
        product.stock_quantity -= quantity
        product.save()

        # Satış Kaydı (Dashboard grafikleri için can damarı burası!)
        Sale.objects.create(
            product=product,
            quantity=quantity,
            price=price
        )
        return Response({"status": "success"}, status=200)
    
    except Product.DoesNotExist:
        # Ürün bulunamazsa hata logu tutmak iyi olur ama şimdilik 404 dönüyoruz
        return Response({"status": "error", "message": "Ürün bulunamadı"}, status=404)