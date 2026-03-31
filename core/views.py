import csv
import json
import pandas as pd
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Sum, F, FloatField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

from .models import Product, Sale
from accounts.models import Profile
from django.contrib.auth import logout
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# -----------------------------------------
# 1. ANA SAYFA (LANDING PAGE)
# -----------------------------------------
def home(request):
    # Eğer kullanıcı zaten giriş yapmışsa, onu direkt dashboard'a yönlendirelim
    if request.user.is_authenticated:
        return redirect('dashboard') 
    return render(request, "core/home.html")

# -----------------------------------------
# 2. CSV YÜKLEME
# -----------------------------------------
@login_required
def upload_sales_csv(request):
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file:
            messages.error(request, "Lütfen bir dosya seçin.")
            return render(request, "core/upload_csv.html")

        try:
            decoded = file.read().decode("utf-8").splitlines()
            reader = csv.DictReader(decoded)
            success = 0
            errors = []

            with transaction.atomic():
                for i, row in enumerate(reader, start=1):
                    try:
                        product_name = row.get("product", "").strip()
                        quantity = float(row.get("quantity", 0))
                        price = float(row.get("price", 0))
                        date_str = row.get("date")

                        if not product_name or not date_str:
                            raise ValueError("Ürün adı veya tarih boş olamaz.")

                        date_obj = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()

                        product, _ = Product.objects.get_or_create(
                            name=product_name,
                            user=request.user,
                            defaults={
                                "cost_price": price * 0.7, 
                                "selling_price": price,
                                "stock_quantity": 50 
                            },
                        )

                        Sale.objects.create(
                            product=product,
                            quantity=quantity,
                            price=price,
                            date=date_obj,
                        )
                        success += 1
                    except Exception as e:
                        errors.append(f"Satır {i}: {str(e)}")

            if success > 0:
                messages.success(request, f"Harika! {success} satış verisi Stockiva'ya işlendi.")
            for err in errors:
                messages.error(request, err)
                
        except Exception as e:
            messages.error(request, f"Dosya formatı hatalı: {str(e)}")

    return render(request, "core/upload_csv.html")

# -----------------------------------------
# 3. DASHBOARD (CFO PANELİ)
# -----------------------------------------
@login_required
def dashboard(request):
    # Profil yoksa otomatik oluştur (Hataları önler)
    profile, created = Profile.objects.get_or_create(user=request.user)
    is_admin = getattr(profile, 'is_admin', False)

    sales_qs = Sale.objects.all() if is_admin else Sale.objects.filter(product__user=request.user)
    user_products = Product.objects.all() if is_admin else Product.objects.filter(user=request.user)

    # Zaman Filtresi
    period = request.GET.get("period", "30")
    today = timezone.now().date()
    
    if period == "7":
        sales_qs = sales_qs.filter(date__gte=today - timedelta(days=7))
    elif period == "30":
        sales_qs = sales_qs.filter(date__gte=today - timedelta(days=30))

    # Temel KPI'lar
    total_products = user_products.count()
    total_sales = sales_qs.count()

    total_revenue = sales_qs.aggregate(
        total=Coalesce(Sum(ExpressionWrapper(F('quantity') * F('price'), output_field=FloatField())), 0.0, output_field=FloatField())
    )['total']

    # Gider Dağılımı ve AOV
    total_cost_val = 0.0
    total_commission_val = 0.0
    total_shipping_val = 0.0
    
    for sale in sales_qs.select_related('product'):
        total_cost_val += float(sale.product.cost_price * sale.quantity)
        total_commission_val += float((sale.price * (sale.product.commission_rate / 100)) * sale.quantity)
        total_shipping_val += float(sale.product.shipping_cost * sale.quantity)

    # Net Kâr = Toplam Gelir - (Maliyet + Komisyon + Kargo)
    profit = total_revenue - total_cost_val - total_commission_val - total_shipping_val
    aov = (total_revenue / total_sales) if total_sales > 0 else 0

    # Aylık Hedef Hesaplaması
    monthly_goal = getattr(profile, 'monthly_revenue_goal', 100000.0)
    goal_progress = (total_revenue / monthly_goal) * 100 if monthly_goal > 0 else 0
    if goal_progress > 100: goal_progress = 100

    # Zaman Bazlı Grafikler (JSON dönüşümleri eklendi - Çökme Engellendi)
    trend_data = sales_qs.values('date').annotate(
        total_qty=Coalesce(Sum('quantity'), 0.0, output_field=FloatField()),
        daily_revenue=Coalesce(Sum(ExpressionWrapper(F('quantity') * F('price'), output_field=FloatField())), 0.0, output_field=FloatField()),
    ).order_by('date')

    trend_labels = json.dumps([str(t['date']) for t in trend_data])
    trend_values = json.dumps([float(t['total_qty']) for t in trend_data])
    revenue_values = json.dumps([float(t['daily_revenue']) for t in trend_data])
    
    # Pratik kâr listesi (Grafik için)
    profit_values = json.dumps([float(t['daily_revenue'] * 0.20) for t in trend_data]) # Örnek kâr trendi

    # En Çok Satan Ürünler Grafiği
    base_sales_data = sales_qs.values('product__name').annotate(
        total_quantity=Coalesce(Sum('quantity'), 0.0, output_field=FloatField()),
        total_profit=Coalesce(Sum(ExpressionWrapper((F('price') - F('product__cost_price')) * F('quantity'), output_field=FloatField())), 0.0, output_field=FloatField())
    )
    top_selling_products = base_sales_data.order_by('-total_quantity')[:10]
    
    product_labels = json.dumps([s['product__name'] for s in top_selling_products])
    product_sales_data = json.dumps([float(s['total_quantity']) for s in top_selling_products])
    top_profit_product = base_sales_data.order_by('-total_profit').first()

    # Stok Yönetimi
    total_stock = user_products.aggregate(total=Coalesce(Sum('stock_quantity'), 0.0, output_field=FloatField()))['total']
    stock_value = user_products.aggregate(total=Coalesce(Sum(ExpressionWrapper(F('stock_quantity') * F('cost_price'), output_field=FloatField())), 0.0, output_field=FloatField()))['total']
    
    critical_stock_products = user_products.filter(stock_quantity__lte=5).order_by('stock_quantity')
    
    # Ölü Stok Tespiti
    sold_product_ids = Sale.objects.filter(product__user=request.user, date__gte=today - timedelta(days=30)).values_list('product_id', flat=True)
    dead_stock = user_products.exclude(id__in=sold_product_ids)

    context = {
        "period": period,
        "total_products": total_products,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "profit": profit,
        "aov": aov,
        "monthly_goal": monthly_goal,
        "goal_progress": goal_progress,
        
        "total_cost_val": total_cost_val,
        "total_commission_val": total_commission_val,
        "total_shipping_val": total_shipping_val,

        # Grafikler
        "trend_labels": trend_labels,
        "trend_values": trend_values,
        "revenue_values": revenue_values,
        "profit_values": profit_values,
        "product_labels": product_labels,
        "product_sales_data": product_sales_data,
        
        "top_profit_product": top_profit_product,
        "total_stock": total_stock,
        "stock_value": stock_value,
        "critical_stock_products": critical_stock_products,
        "dead_stock": dead_stock,
    }
    return render(request, "core/dashboard.html", context)


# -----------------------------------------
# 4. ÜRÜN YÖNETİMİ (STOK HIZI VE KÂR)
# -----------------------------------------
@login_required
def product_management(request):
    user_products = Product.objects.filter(user=request.user)
    today = timezone.now().date()
    fourteen_days_ago = today - timedelta(days=14)
    product_data = []
    
    for product in user_products:
        recent_sales = Sale.objects.filter(
            product=product, date__gte=fourteen_days_ago
        ).aggregate(total=Coalesce(Sum('quantity'), 0.0, output_field=FloatField()))['total']
        
        daily_sales_rate = recent_sales / 14.0
        days_to_stockout = int(product.stock_quantity / daily_sales_rate) if daily_sales_rate > 0 else "Sonsuz"
            
        if product.selling_price > 0:
            commission_amount = product.selling_price * (product.commission_rate / 100)
            net_profit = product.selling_price - product.cost_price - commission_amount - product.shipping_cost
            profit_margin = (net_profit / product.selling_price) * 100
        else:
            net_profit = 0
            profit_margin = 0
            commission_amount = 0

        product_data.append({
            'product': product,
            'recent_sales': recent_sales,
            'daily_rate': round(daily_sales_rate, 2),
            'days_to_stockout': days_to_stockout,
            'net_profit': round(net_profit, 2),
            'commission_amount': round(commission_amount, 2),
            'profit_margin': round(profit_margin, 1)
        })

    return render(request, "core/products.html", {'product_data': product_data, 'total_products': user_products.count()})


# -----------------------------------------
# 5. ÜRÜN GÜNCELLEME (MODAL İÇİN)
# -----------------------------------------
@login_required
def update_product(request, product_id):
    if request.method == "POST":
        product = get_object_or_404(Product, id=product_id, user=request.user)
        try:
            product.cost_price = float(request.POST.get('cost_price', 0).replace(',', '.'))
            product.selling_price = float(request.POST.get('selling_price', 0).replace(',', '.'))
            product.stock_quantity = int(request.POST.get('stock_quantity', 0))
            
            # Komisyon ve Kargo (Varsa al, yoksa 0)
            comm = request.POST.get('commission_rate')
            ship = request.POST.get('shipping_cost')
            if comm: product.commission_rate = float(comm.replace(',', '.'))
            if ship: product.shipping_cost = float(ship.replace(',', '.'))
            
            product.save()
            messages.success(request, f"✅ {product.name} güncellendi! Net kâr yeniden hesaplandı.")
        except ValueError:
            messages.error(request, "❌ Lütfen geçerli sayısal değerler girin.")
            
    return redirect('products')


# -----------------------------------------
# 6. AYARLAR (SETTINGS)
# -----------------------------------------
@login_required
def settings_page(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    password_form = PasswordChangeForm(request.user)

    if request.method == "POST":
        action = request.POST.get('action') 

        if action == 'update_profile':
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.email = request.POST.get('email', '')
            request.user.save()

            profile.phone_number = request.POST.get('phone_number', '')
            profile.two_factor_auth = request.POST.get('two_factor_auth') == 'on'
            profile.email_notifications = request.POST.get('email_notifications') == 'on'
            
            try:
                new_goal = float(request.POST.get('monthly_goal', '100000').replace(',', '.'))
                if new_goal > 0:
                    profile.monthly_revenue_goal = new_goal
            except ValueError:
                pass 
                
            profile.save()
            messages.success(request, "✅ Profil bilgileriniz ve ayarlarınız güncellendi!")
            return redirect('settings')

        elif action == 'update_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user) 
                messages.success(request, "🔒 Şifreniz başarıyla değiştirildi!")
                return redirect('settings')
            else:
                messages.error(request, "❌ Şifre değiştirilemedi. Mevcut şifrenizi kontrol edin.")

    context = {
        "profile": profile,
        "password_form": password_form,
    }
    return render(request, "core/settings.html", context)


# -----------------------------------------
# 7. RAPOR İNDİRME (EXCEL EXPORT)
# -----------------------------------------
@login_required
def export_sales_excel(request):
    sales = Sale.objects.filter(product__user=request.user).select_related('product')
    data = []
    
    for s in sales:
        revenue = s.quantity * s.price
        cost = s.product.cost_price * s.quantity
        commission = (s.price * (s.product.commission_rate / 100)) * s.quantity
        shipping = s.product.shipping_cost * s.quantity
        net_profit = revenue - cost - commission - shipping

        data.append({
            "Ürün Adı": s.product.name,
            "Satış Adedi": s.quantity,
            "Birim Satış Fiyatı (₺)": s.price,
            "Toplam Gelir (₺)": revenue,
            "Toplam Maliyet (₺)": cost,
            "Pazar Yeri Komisyonu (₺)": commission,
            "Kargo Gideri (₺)": shipping,
            "Net Kâr (₺)": net_profit,
            "Satış Tarihi": s.date,
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=Stockiva_Satis_Raporu.xlsx'
    df.to_excel(response, index=False)
    return response


# -----------------------------------------
# 8. KÜÇÜK WIDGET'LAR
# -----------------------------------------
@login_required
def sales_widget(request):
    total_sales = Sale.objects.filter(product__user=request.user).count()
    return render(request, "widgets/sales_widget.html", {"total_sales": total_sales})

# -----------------------------------------
# 9. GÜVENLİ ÇIKIŞ YAP (CUSTOM LOGOUT)
# -----------------------------------------
def custom_logout(request):
    logout(request) # Kullanıcının oturumunu (session) anında siler
    messages.info(request, "👋 Başarıyla çıkış yaptınız. Görüşmek üzere!")
    return redirect('home') # Çıkış yapınca ana sayfaya yolla



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