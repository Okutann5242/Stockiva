"""
core/api_views.py — DRF tabanlı API endpoint'leri.

NOT: Shopier webhook'u buradan kaldırıldı.
Tek gerçek webhook endpoint'i core/views.py'deki shopier_webhook fonksiyonudur
(CSRF exempt, imza doğrulamalı). Bu dosyadaki versiyon ölü kod olduğu için silindi.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Product, Sale


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_list_api(request):
    """
    Kullanıcının ürünlerini JSON olarak döner.
    Mobil uygulama veya harici entegrasyon için kullanılabilir.
    """
    products = Product.objects.filter(user=request.user).values(
        'id', 'name', 'cost_price', 'selling_price',
        'stock_quantity', 'commission_rate', 'shipping_cost', 'category'
    )
    return Response({'products': list(products)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_summary_api(request):
    """
    Son 30 günün satış özetini döner.
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum, FloatField, ExpressionWrapper, F
    from django.db.models.functions import Coalesce

    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    sales = Sale.objects.filter(
        product__user=request.user,
        date__gte=thirty_days_ago
    ).aggregate(
        total_revenue=Coalesce(
            Sum(ExpressionWrapper(F('quantity') * F('price'), output_field=FloatField())),
            0.0, output_field=FloatField()
        ),
        total_quantity=Coalesce(Sum('quantity'), 0.0, output_field=FloatField()),
    )
    return Response(sales)
