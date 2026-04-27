# ==============================================================================
# 📦 STOCKIVA — CORE VIEWS
# Tüm import'lar tek blokta, dosya ortasında tekrar yok.
# ==============================================================================

import csv
import json
import logging
import os

import iyzipay
import pandas as pd
import requests

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum, F, FloatField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django_ratelimit.decorators import ratelimit

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .decorators import pro_required
from .models import Product, Sale, send_stock_alert
from .utils import call_groq, verify_shopier_signature, safe_float, safe_int
from accounts.models import Profile
from django.urls import reverse
from django.shortcuts import render, redirect
from django.contrib import messages
import groq # Groq veya Gemini API kullanıyorsan
import google.generativeai as genai
from django.conf import settings
from django.shortcuts import render, redirect
from .models import SupportTicket
import csv
import logging
import magic  # Dosya içeriğini kontrol etmek için (pip install python-magic)
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from .models import Product, Sale
from .utils import safe_float, safe_int # Mevcut yardımcı fonksiyonların
logger = logging.getLogger('core')


# ==============================================================================
# 🏠 1. ANA SAYFA VE ÇIKIŞ
# ==============================================================================

def home(request):
    """Giriş yapılmışsa dashboard'a atar."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')


@require_POST  # DÜZELTME: Logout artık sadece POST ile çalışır (CSRF güvenliği)
def custom_logout(request):
    """Kullanıcı oturumunu güvenli şekilde kapatır."""
    logout(request)
    messages.info(request, '👋 Başarıyla çıkış yaptınız. Görüşmek üzere!')
    return redirect('home')


# ==============================================================================
# 📊 2. DASHBOARD
# ==============================================================================

@login_required
def dashboard(request):
    """
    Ana KPI paneli. Gelir, kâr, stok durumu ve grafik verilerini hazırlar.
    DÜZELTME:
    - Kâr hesabı Product model metodları üzerinden yapılıyor (tutarlılık)
    - Grafik kâr değeri artık gerçek veri (sabit %20 değil)
    - Admin için dead_stock hesabı düzeltildi
    """
    profile, _ = Profile.objects.get_or_create(user=request.user)
    is_pro = profile.check_subscription()
    is_admin = getattr(profile, 'is_admin', False)

    # Veri kapsamı (admin tüm veriyi, normal kullanıcı sadece kendininkini görür)
    sales_qs = Sale.objects.all() if is_admin else Sale.objects.filter(product__user=request.user)
    user_products = Product.objects.all() if is_admin else Product.objects.filter(user=request.user)

    # Zaman filtresi
    period = request.GET.get('period', '30')
    today = timezone.now().date()
    if period == '7':
        sales_qs = sales_qs.filter(date__gte=today - timedelta(days=7))
    elif period == '30':
        sales_qs = sales_qs.filter(date__gte=today - timedelta(days=30))

    # ── Temel KPI'lar ──────────────────────────────────────────────────────────
    total_products = user_products.count()
    total_sales = sales_qs.count()
    total_revenue = sales_qs.aggregate(
        total=Coalesce(
            Sum(ExpressionWrapper(F('quantity') * F('price'), output_field=FloatField())),
            0.0, output_field=FloatField()
        )
    )['total']

    # ── Gider Döngüsü ──────────────────────────────────────────────────────────
    # select_related ile N+1 önlendi. Kâr hesabı Sale.get_profit() üzerinden
    # gidiyor, formül tek yerden (models.py) yönetiliyor.
    total_cost_val = 0.0
    total_commission_val = 0.0
    total_shipping_val = 0.0
    total_profit_val = 0.0

    for sale in sales_qs.select_related('product'):
        qty = sale.quantity or 0
        price = sale.price or 0
        cost_price = sale.product.cost_price or 0
        comm_rate = sale.product.commission_rate or 0
        ship_cost = sale.product.shipping_cost or 0

        revenue_line = price * qty
        cost_line = cost_price * qty
        commission_line = (price * comm_rate / 100) * qty
        shipping_line = ship_cost * qty
        profit_line = revenue_line - cost_line - commission_line - shipping_line

        total_cost_val += cost_line
        total_commission_val += commission_line
        total_shipping_val += shipping_line
        total_profit_val += profit_line

    aov = (total_revenue / total_sales) if total_sales > 0 else 0

    # ── Aylık Hedef ────────────────────────────────────────────────────────────
    monthly_goal = profile.monthly_revenue_goal or 100000.0
    goal_progress = min((total_revenue / monthly_goal) * 100, 100) if monthly_goal > 0 else 0

    # ── Grafik Verileri ────────────────────────────────────────────────────────
    # DÜZELTME: profit_values artık gerçek kâr verisi (önceki sabit %20 kaldırıldı)
    # Her gün için kârı product maliyet/komisyon/kargo bilgisiyle hesaplıyoruz.
    # Bu yüzden ayrı bir döngü yerine annotation kullanıyoruz.
    trend_data = (
        sales_qs
        .values('date')
        .annotate(
            total_qty=Coalesce(Sum('quantity'), 0.0, output_field=FloatField()),
            daily_revenue=Coalesce(
                Sum(ExpressionWrapper(F('quantity') * F('price'), output_field=FloatField())),
                0.0, output_field=FloatField()
            ),
            daily_cost=Coalesce(
                Sum(ExpressionWrapper(F('quantity') * F('product__cost_price'), output_field=FloatField())),
                0.0, output_field=FloatField()
            ),
            daily_commission=Coalesce(
                Sum(ExpressionWrapper(
                    F('quantity') * F('price') * F('product__commission_rate') / 100.0,
                    output_field=FloatField()
                )),
                0.0, output_field=FloatField()
            ),
            daily_shipping=Coalesce(
                Sum(ExpressionWrapper(F('quantity') * F('product__shipping_cost'), output_field=FloatField())),
                0.0, output_field=FloatField()
            ),
        )
        .order_by('date')
    )

    trend_labels = json.dumps([str(t['date']) for t in trend_data])
    trend_values = json.dumps([float(t['total_qty']) for t in trend_data])
    revenue_values = json.dumps([float(t['daily_revenue']) for t in trend_data])
    # Gerçek kâr = gelir - maliyet - komisyon - kargo
    profit_values = json.dumps([
        float(t['daily_revenue'] - t['daily_cost'] - t['daily_commission'] - t['daily_shipping'])
        for t in trend_data
    ])

    # ── Ürün Bazlı Analizler ───────────────────────────────────────────────────
    base_sales_data = sales_qs.values('product__name').annotate(
        total_quantity=Coalesce(Sum('quantity'), 0.0, output_field=FloatField()),
        total_profit=Coalesce(
            Sum(ExpressionWrapper(
                (F('price') - F('product__cost_price')) * F('quantity'),
                output_field=FloatField()
            )),
            0.0, output_field=FloatField()
        )
    )
    top_selling_products = base_sales_data.order_by('-total_quantity')[:10]
    product_labels = json.dumps([s['product__name'] for s in top_selling_products])
    product_sales_data = json.dumps([float(s['total_quantity']) for s in top_selling_products])
    top_profit_product = base_sales_data.order_by('-total_profit').first()

    # ── Stok Yönetimi ──────────────────────────────────────────────────────────
    total_stock = user_products.aggregate(
        total=Coalesce(Sum('stock_quantity'), 0.0, output_field=FloatField())
    )['total']
    stock_value = user_products.aggregate(
        total=Coalesce(
            Sum(ExpressionWrapper(F('stock_quantity') * F('cost_price'), output_field=FloatField())),
            0.0, output_field=FloatField()
        )
    )['total']
    critical_stock_products = user_products.filter(stock_quantity__lte=5).order_by('stock_quantity')

    # DÜZELTME: dead_stock — admin içinse tüm kullanıcıların ürünleri baz alınır
    sold_product_ids = (
        Sale.objects
        .filter(date__gte=today - timedelta(days=30))
        .filter(
            product__in=user_products  # Admin'de de doğru kapsamda kalır
        )
        .values_list('product_id', flat=True)
        .distinct()
    )
    dead_stock = user_products.exclude(id__in=sold_product_ids)

    context = {
        'period': period,
        'total_products': total_products,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'profit': total_profit_val,
        'aov': aov,
        'monthly_goal': monthly_goal,
        'goal_progress': goal_progress,
        'total_cost_val': total_cost_val,
        'total_commission_val': total_commission_val,
        'total_shipping_val': total_shipping_val,
        'trend_labels': trend_labels,
        'trend_values': trend_values,
        'revenue_values': revenue_values,
        'profit_values': profit_values,
        'product_labels': product_labels,
        'product_sales_data': product_sales_data,
        'top_profit_product': top_profit_product,
        'total_stock': total_stock,
        'stock_value': stock_value,
        'critical_stock_products': critical_stock_products,
        'dead_stock': dead_stock,
        'profile': profile,
        'is_pro': is_pro,
        'subscription_days': profile.subscription_days_remaining,
    }
    return render(request, 'core/dashboard.html', context)


# ==============================================================================
# 📦 3. ÜRÜN YÖNETİMİ
# ==============================================================================

@login_required
def product_management(request):
    """
    Ürün hızı ve kâr marjlarını listeler.
    DÜZELTME: N+1 query giderildi. Tüm satış verileri tek sorguda çekilip
    Python dict'e dönüştürüldü, ardından döngüde lookup yapılıyor.
    """
    profile, _ = Profile.objects.get_or_create(user=request.user)
    is_pro = profile.check_subscription()

    user_products = Product.objects.filter(user=request.user)
    today = timezone.now().date()
    fourteen_days_ago = today - timedelta(days=14)

    # DÜZELTME: N+1 → tek toplu sorgu
    recent_sales_qs = (
        Sale.objects
        .filter(product__user=request.user, date__gte=fourteen_days_ago)
        .values('product_id')
        .annotate(total=Coalesce(Sum('quantity'), 0.0, output_field=FloatField()))
    )
    sales_lookup = {s['product_id']: s['total'] for s in recent_sales_qs}

    product_data = []
    for product in user_products:
        recent_sales = sales_lookup.get(product.id, 0.0)
        daily_sales_rate = recent_sales / 14.0

        if daily_sales_rate > 0 and (product.stock_quantity or 0) > 0:
            days_to_stockout = int((product.stock_quantity or 0) / daily_sales_rate)
        else:
            days_to_stockout = None  # Template'te "Sonsuz" olarak gösterilecek

        net_profit = product.get_net_profit_per_unit()
        commission_amount = product.get_commission_amount()
        profit_margin = product.get_profit_margin()

        product_data.append({
            'product': product,
            'recent_sales': recent_sales,
            'daily_rate': round(daily_sales_rate, 2),
            'days_to_stockout': days_to_stockout,
            'net_profit': round(net_profit, 2),
            'commission_amount': round(commission_amount, 2),
            'profit_margin': round(profit_margin, 1),
        })

    return render(request, 'core/products.html', {
        'product_data': product_data,
        'total_products': user_products.count(),
        'profile': profile,
        'is_pro': is_pro,
    })


@login_required
@require_POST
def update_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, user=request.user)
    try:
        # Değerleri alıyoruz
        cost = safe_float(request.POST.get('cost_price', 0))
        selling = safe_float(request.POST.get('selling_price', 0))
        stock = safe_int(request.POST.get('stock_quantity', 0))
        
        # --- GÜVENLİK KONTROLÜ (Burası Çok Önemli) ---
        if cost < 0 or selling < 0 or stock < 0:
            messages.error(request, '❌ Maliyet, fiyat veya stok miktarı negatif olamaz!')
            return redirect('products')
        # -------------------------------------------

        product.cost_price = cost
        product.selling_price = selling
        product.stock_quantity = stock
        
        # Diğer alanlar aynı kalabilir...
        product.commission_rate = safe_float(request.POST.get('commission_rate', product.commission_rate))
        product.shipping_cost = safe_float(request.POST.get('shipping_cost', product.shipping_cost))
        product.category = request.POST.get('category', product.category).strip() or 'Genel'
        
        product.save()
        messages.success(request, f'✅ {product.name} başarıyla güncellendi!')

    except Exception as e:
        logger.error(f'Ürün güncelleme hatası (id={product_id}): {e}')
        messages.error(request, '❌ Güncelleme sırasında bir hata oluştu.')
    
    return redirect('products')


@login_required
@require_POST
def delete_product(request, product_id):
    """Ürünü ve bağlı satışlarını siler."""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    name = product.name
    product.delete()
    messages.success(request, f'🗑️ "{name}" ve bağlı satış kayıtları silindi.')
    return redirect('products')


# ==============================================================================
# 🤖 4. YAPAY ZEKA ANALİZİ
# ==============================================================================

@login_required
@ratelimit(key='user', rate='5/d', block=False)
def ai_shop_analysis(request):
    """
    Tüm dükkanın genel AI analizini yapar.
    DÜZELTME: @pro_required yerine manuel check ve check_subscription() eklendi.
    """
    # 1. PRO Kontrolü (Hata buradaydı, şimdi kesinleşti)
    profile = request.user.profile
    if not profile.check_subscription(): # Kendi yazdığın metotla kontrol et
        messages.warning(request, '🚀 Bu özellik sadece PRO üyelerimize özeldir. Hemen yükseltin!')
        return redirect('settings')

    # 2. Hız Sınırı (Rate Limit) Kontrolü
    if getattr(request, 'limited', False):
        messages.error(request, '⏳ Günlük analiz kotanı doldurdun. Yarın tekrar dene.')
        return redirect('dashboard')

    # 3. Ürün Verilerini Hazırla
    products = Product.objects.filter(user=request.user)
    if not products.exists():
        messages.info(request, 'Henüz ürün eklemedin. Analiz için önce ürün ekle.')
        return redirect('dashboard')

    # Hesaplamalar
    total_stock_value = sum((p.stock_quantity or 0) * (p.selling_price or 0) for p in products)
    low_stock = [p.name for p in products if (p.stock_quantity or 0) < 5]

    product_lines = []
    for p in products:
        level = 'Lüks' if (p.selling_price or 0) > 10000 else 'Orta' if (p.selling_price or 0) > 1000 else 'Ekonomik'
        margin = p.get_profit_margin()
        product_lines.append(
            f'- {p.name}: {p.stock_quantity} adet, {p.selling_price}₺ ({level}), '
            f'Kâr marjı: %{margin:.1f}'
        )

    # 4. Yapay Zeka İstemi
    prompt = f"""
    Sen bir e-ticaret danışmanısın. Aşağıdaki dükkan verilerini analiz et:
    Toplam Stok Değeri: {total_stock_value:.0f} ₺
    Kritik Stok (5 altı): {', '.join(low_stock) if low_stock else 'Yok'}
    Ürün Listesi:
    {chr(10).join(product_lines)}

    GÖREV:
    1. Stok verimliliğini değerlendir (sermaye yönetimi açısından).
    2. Hangi ürünlere odaklanılmalı, hangilerinden çıkılmalı?
    3. En düşük kâr marjlı ürünleri özel olarak belirt.
    4. Somut ve uygulanabilir 3 öneri sun.
    Türkçe yaz, net ve profesyonel ol.
    """

    analysis_text = call_groq(prompt, temperature=0.7)
    if analysis_text is None:
        analysis_text = 'Yapay zeka şu an yanıt veremiyor. Lütfen birkaç dakika sonra tekrar dene.'

    return render(request, 'core/ai_analysis.html', {'analysis': analysis_text})


@login_required
@ratelimit(key='user', rate='15/d', block=False)
def ai_product_analysis(request, product_id):
    """
    Tek ürün için AI analizi (AJAX endpoint).
    DÜZELTME: Groq çağrısı call_groq() ile yapılıyor (DRY).
    """
    if getattr(request, 'limited', False):
        return JsonResponse({'error': '⏳ Günlük ürün analiz kotanı doldurdun.'}, status=429)

    product = get_object_or_404(Product, id=product_id, user=request.user)

    net_profit = product.get_net_profit_per_unit()
    margin = product.get_profit_margin()
    context_label = 'Yüksek değerli ürün' if (product.selling_price or 0) > 5000 else 'Standart ürün'

    prompt = f"""
Sen bir e-ticaret stratejistisin. Bu ürünü analiz et:

Ürün: {product.name} ({context_label})
Maliyet: {product.cost_price}₺ | Satış: {product.selling_price}₺
Komisyon: %{product.commission_rate} | Kargo: {product.shipping_cost}₺
Net Kâr/Birim: {net_profit:.2f}₺ | Kâr Marjı: %{margin:.1f}
Mevcut Stok: {product.stock_quantity} adet

YAPILACAKLAR:
1. Bu stok seviyesi bu fiyata göre mantıklı mı?
2. Kâr marjını yorumla (sektör ortalamasıyla karşılaştır).
3. 1 somut aksiyon öner.
Türkçe, net ve kısa yaz.
"""

    analysis_text = call_groq(prompt, temperature=0.7, timeout=10)
    if analysis_text is None:
        return JsonResponse({'error': 'Yapay zeka şu an yanıt veremiyor.'}, status=500)

    return JsonResponse({'analysis': analysis_text})



# ==============================================================================
# 💳 5. ÖDEME SİSTEMİ (İYZİCO)
# ==============================================================================

@login_required
def checkout(request):
    """İyzico ödeme formunu başlatır."""
    options = {
        'api_key': settings.IYZICO_API_KEY,
        'secret_key': settings.IYZICO_SECRET_KEY,
        'base_url': settings.IYZICO_BASE_URL,
    }

    # DÜZELTME: callbackUrl artık settings.BASE_URL'den geliyor (hardcoded localhost yok)
    callback_url = request.build_absolute_uri(reverse('iyzico_callback'))

    payment_request = {
        'locale': 'tr',
        'conversationId': str(request.user.id),
        'price': '199.0',
        'paidPrice': '199.0',
        'currency': 'TRY',
        'basketId': f'STOCKIVA-PRO-{request.user.id}',
        'paymentGroup': 'PRODUCT',
        'callbackUrl': callback_url,
        'buyer': {
            'id': str(request.user.id),
            'name': request.user.first_name or request.user.username,
            'surname': request.user.last_name or '-',
            'email': request.user.email,
            'identityNumber': '11111111111',  # TODO: Kullanıcıdan alınacak
            'city': 'Istanbul',
            'country': 'Turkey',
            'registrationAddress': 'Türkiye',
            'zipCode': '34000',
        },
        'shippingAddress': {
            'contactName': request.user.username,
            'city': 'Istanbul',
            'country': 'Turkey',
            'address': 'Türkiye',
            'zipCode': '34000',
        },
        'billingAddress': {
            'contactName': request.user.username,
            'city': 'Istanbul',
            'country': 'Turkey',
            'address': 'Türkiye',
            'zipCode': '34000',
        },
        'basketItems': [
            {
                'id': 'STOCKIVA-PRO',
                'name': 'Stockiva PRO Üyelik (30 Gün)',
                'category1': 'Yazılım',
                'itemType': 'VIRTUAL',
                'price': '199.0',
            }
        ],
    }

    try:
        checkout_form = iyzipay.CheckoutFormInitialize().create(payment_request, options)
        content_json = json.loads(checkout_form.read().decode('utf-8'))

        if content_json.get('status') == 'success':
            profile = request.user.profile
            profile.iyzico_token = content_json.get('token')
            profile.save(update_fields=['iyzico_token'])
            return render(request, 'core/checkout.html', {
                'payment_form': content_json.get('checkoutFormContent')
            })

        error_msg = content_json.get('errorMessage', 'Bilinmeyen hata')
        logger.error(f'İyzico checkout hatası (user={request.user.id}): {error_msg}')
        messages.error(request, f'Ödeme başlatılamadı: {error_msg}')
        return redirect('settings')

    except Exception as e:
        logger.error(f'İyzico checkout exception (user={request.user.id}): {e}')
        messages.error(request, 'Ödeme sistemiyle bağlantı kurulamadı. Lütfen tekrar dene.')
        return redirect('settings')


@csrf_exempt
def iyzico_callback(request):
    """
    İyzico'dan gelen ödeme sonucu callback'i.
    DÜZELTME: DoesNotExist exception artık handle ediliyor (500 hatası yok).
    """
    if request.method != 'POST':
        return redirect('settings')

    token = request.POST.get('token')
    if not token:
        logger.warning('İyzico callback: token yok')
        return redirect('settings')

    options = {
        'api_key': settings.IYZICO_API_KEY,
        'secret_key': settings.IYZICO_SECRET_KEY,
        'base_url': settings.IYZICO_BASE_URL,
    }

    try:
        checkout_form = iyzipay.CheckoutForm().retrieve({'token': token}, options)
        result = json.loads(checkout_form.read().decode('utf-8'))

        if result.get('status') == 'success' and result.get('paymentStatus') == 'SUCCESS':
            try:
                profile = Profile.objects.get(iyzico_token=token)
            except Profile.DoesNotExist:
                logger.error(f'İyzico callback: token eşleşmedi — {token[:20]}...')
                messages.error(request, 'Ödeme doğrulanamadı. Lütfen destek ile iletişime geçin.')
                return redirect('settings')

            profile.is_pro = True
            profile.auto_renew = True
            profile.subscription_end_date = timezone.now() + timedelta(days=30)
            profile.iyzico_token = ''  # Token'ı hemen temizle
            profile.save(update_fields=['is_pro', 'subscription_end_date', 'iyzico_token','auto_renew'])

            # Fatura maili
            try:
                mail_html = render_to_string('core/payment_success_email.html', {
                    'user': profile.user,
                    'end_date': profile.subscription_end_date,
                })
                send_mail(
                    '✅ Stockiva PRO Üyeliğiniz Aktif!',
                    'Ödemeniz onaylandı.',
                    settings.DEFAULT_FROM_EMAIL,
                    [profile.user.email],
                    html_message=mail_html,
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f'PRO aktivasyon maili gönderilemedi (user={profile.user.id}): {e}')

            logger.info(f'PRO aktif edildi: {profile.user.username}')
            messages.success(request, f'🎉 Tebrikler {profile.user.first_name or profile.user.username}! PRO üyeliğin aktif!')
            return redirect('dashboard')

    except Exception as e:
        logger.error(f'İyzico callback genel hata: {e}')

    messages.error(request, 'Ödeme işlemi tamamlanamadı. Lütfen destek ile iletişime geçin.')
    return redirect('settings')


# ==============================================================================
# 🔗 6. ENTEGRASYONLAR (SHOPIER)
# ==============================================================================

@csrf_exempt
def shopier_webhook(request):
    if request.method != 'POST':
        return HttpResponse(status=400)

    p_name = request.POST.get('product_name', '').strip()
    qty = safe_int(request.POST.get('res_quantity', 1), default=1)
    price = safe_float(request.POST.get('total_order_value', 0))
    shopier_key = request.POST.get('api_key', '').strip()

    if not p_name:
        return HttpResponse('Ürün adı boş', status=400)

    try:
        # 1. KRİTİK DÜZELTME: API Key yoksa anında işlemi reddet!
        if not shopier_key:
            logger.warning('Shopier webhook: API key eksik gönderildi.')
            return HttpResponse('API key gerekli', status=401)

        try:
            profile = Profile.objects.select_related('user').get(shopier_api_key=shopier_key)
        except Profile.DoesNotExist:
            logger.warning(f'Shopier webhook: API key eşleşmedi')
            return HttpResponse('API key tanınmadı', status=403)

        # 2. Kullanıcının kendi secret'ıyla imzayı doğrula
        if not verify_shopier_signature(request, profile.shopier_webhook_secret):
            logger.warning(f'Shopier webhook: geçersiz imza (user={profile.user.username})')
            return HttpResponse('Geçersiz İmza', status=403)

        # 3. KRİTİK DÜZELTME: Sadece ve sadece API anahtarı eşleşen kullanıcının ürününü ara!
        product = Product.objects.filter(
            name__icontains=p_name,
            user=profile.user
        ).first()

        if not product:
            return HttpResponse('Ürün bulunamadı', status=404)

        # İşlem başarılıysa stok düş ve satışı kaydet
        with transaction.atomic():
            Product.objects.filter(id=product.id).update(
                stock_quantity=F('stock_quantity') - qty
            )
            product.refresh_from_db()
            Sale.objects.create(
                product=product,
                quantity=qty,
                price=price,
                date=timezone.now().date(),
            )

        send_stock_alert(product)
        return HttpResponse('Başarılı', status=200)

    except Exception as e:
        logger.error(f'Shopier webhook hatası: {e}')
        return HttpResponse(str(e), status=500)

@login_required
@require_POST
def delete_product(request, product_id):
    """Ürünü ve bağlı tüm satış kayıtlarını kalıcı olarak siler."""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    name = product.name
    product.delete()
    messages.success(request, f'🗑️ "{name}" ve buna bağlı tüm geçmiş satış verileri başarıyla silindi.')
    return redirect('products')

@login_required
@require_POST
def sync_shopier(request):
    """
    Shopier API'den gelen hiyerarşik veriyi (priceData -> price) çözen fonksiyon.
    """
    api_key = request.POST.get('shopier_api_key', '').strip()
    profile = request.user.profile
    profile.shopier_api_key = api_key
    profile.save(update_fields=['shopier_api_key'])

    url = 'https://api.shopier.com/v1/products'
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json()
            synced = 0
            
            for item in items:
                title = item.get('title', '').strip()
                if not title:
                    continue

                # 💰 Fiyat Çekme (Hata buradaydı: priceData içindeki price'ı almalıyız)
                price_info = item.get('priceData', {})
                raw_price = price_info.get('price', 0)
                
                # 📦 Stok Çekme (Senin verinde direkt 'stockQuantity' olarak geliyor)
                raw_stock = item.get('stockQuantity', 0)

                # Sayıya Çevirme (Güvenli yöntem)
                try:
                    selling_price = float(raw_price)
                    stock_quantity = int(raw_stock)
                except (ValueError, TypeError):
                    selling_price = 0.0
                    stock_quantity = 0

                # Veritabanına Güncelle veya Oluştur
                Product.objects.update_or_create(
                    name=title,
                    user=request.user,
                    defaults={
                        'selling_price': selling_price,
                        'stock_quantity': stock_quantity,
                        'category': 'Genel' # Shopier'den gelen kategoriler liste olduğu için şimdilik Genel diyoruz
                    }
                )
                synced += 1
            
            messages.success(request, f'✅ {synced} ürünün verileri (Fiyat: ₺{selling_price}, Stok: {stock_quantity}) güncellendi!')
        else:
            messages.error(request, f'Shopier Bağlantı Hatası: {response.status_code}')
            
    except Exception as e:
        logger.error(f'sync_shopier hatası: {e}')
        messages.error(request, f'Sistem hatası: {e}')

    return redirect('settings')


# ==============================================================================
# ⚙️ 7. AYARLAR VE VERİ AKTARIMI
# ==============================================================================




@login_required
def upload_sales_csv(request):
    """
    CSV verisi yükler. MIME tipi, dosya boyutu, satır sayısı 
    ve veri temizliği kontrolleri ile zırhlandırılmıştır.
    """
    if request.method != 'POST':
        return render(request, 'core/upload_csv.html')

    file = request.FILES.get('file')
    if not file:
        messages.error(request, 'Lütfen bir dosya seçin.')
        return render(request, 'core/upload_csv.html')

    # 1. DOSYA BOYUTU KONTROLÜ (5 MB)
    if file.size > 5 * 1024 * 1024:
        messages.error(request, 'Dosya boyutu 5 MB\'ı geçemez.')
        return render(request, 'core/upload_csv.html')

    # 2. MIME TYPE (İÇERİK) KONTROLÜ - Sadece uzantıya değil, içeriğe bakıyoruz
    initial_content = file.read(2048)
    file.seek(0)
    mime = magic.from_buffer(initial_content, mime=True)
    
    # Bazı sistemler CSV'yi text/plain veya application/vnd.ms-excel olarak görebilir
    allowed_mimes = ['text/plain', 'text/csv', 'application/csv', 'application/vnd.ms-excel']
    if mime not in allowed_mimes:
        logger.warning(f"Zararlı dosya girişimi (user={request.user.id}): {mime}")
        messages.error(request, 'Geçersiz dosya formatı. Lütfen gerçek bir CSV dosyası yükleyin.')
        return render(request, 'core/upload_csv.html')

    try:
        # UTF-8 BOM ve Decode işlemleri
        decoded = file.read().decode('utf-8-sig').splitlines()
        
        # 3. SATIR SAYISI LİMİTİ (DoS Saldırısını Önlemek İçin)
        if len(decoded) > 1000:
            messages.error(request, 'Güvenlik nedeniyle tek seferde en fazla 1000 satır yükleyebilirsiniz.')
            return render(request, 'core/upload_csv.html')

        reader = csv.DictReader(decoded)
        success = 0
        errors = []

        # Veritabanı tutarlılığı için atomic işlem
        with transaction.atomic():
            for i, row in enumerate(reader, start=1):
                try:
                    # 4. VERİ TEMİZLİĞİ VE XSS KORUMASI (strip ve HTML escape mantığı)
                    p_name = (
                        row.get('product') or row.get('Ürün') or
                        row.get('Ürün Adı') or row.get('urun_adi') or ''
                    ).strip()[:200]  # Uzunluk limiti koyarak veritabanını koruyoruz
                    
                    if not p_name:
                        p_name = 'İsimsiz Ürün'

                    qty = safe_float(
                        row.get('quantity') or row.get('Adet') or row.get('Stok') or 1
                    ) or 1.0

                    price = safe_float(
                        row.get('price') or row.get('Fiyat') or row.get('Ürün Fiyatı') or 0
                    )

                    # Tarih İşlemleri
                    date_str = (row.get('date') or row.get('Tarih') or '').strip()
                    try:
                        date_obj = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        date_obj = timezone.now().date()

                    # 5. IDOR VE YETKİ KONTROLÜ (user=request.user)
                    product, created = Product.objects.get_or_create(
                        name=p_name,
                        user=request.user,
                        defaults={
                            'cost_price': 0.0,
                            'selling_price': price if price > 0 else 0.0,
                            'stock_quantity': 0,
                            'category': 'Genel',
                        }
                    )

                    # Satış kaydı oluşturma
                    Sale.objects.create(
                        product=product,
                        quantity=qty if qty > 0 else 1.0,
                        price=price if price > 0 else 0.0,
                        date=date_obj,
                    )
                    success += 1

                    # Performans dostu stok uyarısı
                    if success % 10 == 0:
                        send_stock_alert(product)

                except Exception as e:
                    errors.append(f'Satır {i}: {str(e)}')

        # Geri Bildirimler
        if success > 0:
            messages.success(request, f'✅ {success} kayıt başarıyla işlendi!')
        if errors:
            messages.warning(request, f'⚠️ {len(errors)} satırda hata çıktı.')
            logger.warning(f'CSV yükleme hataları (user={request.user.id}): {errors[:10]}')

    except UnicodeDecodeError:
        messages.error(request, 'Dosya okuma hatası! Lütfen UTF-8 formatında bir dosya yükleyin.')
    except Exception as e:
        logger.error(f'CSV genel hata: {e}')
        messages.error(request, 'Dosya işlenirken beklenmedik bir hata oluştu.')

    return render(request, 'core/upload_csv.html')

@login_required
def export_sales_excel(request):
    """Finansal raporu Excel olarak indirir."""
    sales = (
        Sale.objects
        .filter(product__user=request.user)
        .select_related('product')
        .order_by('-date')
    )
    data = []
    for s in sales:
        rev = s.get_revenue()
        cost = s.get_cost()
        profit = s.get_profit()
        data.append({
            'Ürün': s.product.name,
            'Kategori': s.product.category,
            'Adet': s.quantity,
            'Birim Fiyat (₺)': s.price,
            'Gelir (₺)': round(rev, 2),
            'Maliyet (₺)': round(cost, 2),
            'Komisyon (₺)': round((s.price or 0) * (s.product.commission_rate or 0) / 100 * (s.quantity or 0), 2),
            'Kargo (₺)': round((s.product.shipping_cost or 0) * (s.quantity or 0), 2),
            'Net Kâr (₺)': round(profit, 2),
            'Tarih': s.date,
        })

    df = pd.DataFrame(data)
    http_response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    http_response['Content-Disposition'] = 'attachment; filename=Stockiva_Finansal_Rapor.xlsx'
    df.to_excel(http_response, index=False, sheet_name='Satışlar')
    return http_response


@login_required
def settings_page(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. Profil ve Ciro Güncelleme
        if action == 'update_profile':
            request.user.first_name = request.POST.get('first_name', '').strip()
            request.user.last_name = request.POST.get('last_name', '').strip()
            request.user.email = request.POST.get('email', request.user.email).strip()
            request.user.save()
            
            profile.phone_number = request.POST.get('phone_number', '').strip()
            
            goal = request.POST.get('monthly_revenue_goal')
            if goal:
                profile.monthly_revenue_goal = float(goal)
            
            profile.email_notifications = request.POST.get('email_notifications') == 'on'
            
            new_secret = request.POST.get('shopier_webhook_secret')
            if new_secret is not None:
                profile.shopier_webhook_secret = new_secret.strip()
            
            profile.save()
            messages.success(request, '✅ Profil ve ciro hedefi güncellendi.')

        # 2. Şifre Güncelleme
        elif action == 'update_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, '🔐 Şifre güncellendi.')
            else:
                messages.error(request, '❌ Hata: Formu kontrol et.')

        # 3. Aboneliği Durdur (Sadece Yenilemeyi Kapatır, PRO'yu Bitirmez)
        elif action == 'cancel_subscription':
            if profile.is_pro:
                profile.auto_renew = False
                profile.save(update_fields=['auto_renew'])
                messages.warning(request, '📅 Yenileme kapatıldı. Ay sonuna kadar PRO devam edecek.')
            else:
                messages.error(request, 'Aktif abonelik bulunamadı.')

        # 4. Aboneliği Tekrar Aç (Geri Dönmek İsteyenler İçin)
        elif action == 'reactivate_subscription':
            if profile.is_pro:
                profile.auto_renew = True
                profile.save(update_fields=['auto_renew'])
                messages.success(request, '🚀 Yenileme tekrar açıldı, kesintisiz devam!')

        return redirect('settings')

    # GET isteğinde sayfayı yükle
    return render(request, 'core/settings.html', {
        'profile': profile,
        'password_form': password_form,
    })

@login_required
def sales_widget(request):
    """Satış sayısını gösteren küçük widget."""
    total_sales = Sale.objects.filter(product__user=request.user).count()
    return render(request, 'core/widgets/sales_widget.html', {'total_sales': total_sales})


@login_required
@require_POST
def add_product_manual(request):
    name = request.POST.get('name')
    cost = safe_float(request.POST.get('cost_price', 0))
    price = safe_float(request.POST.get('selling_price', 0))
    stock = safe_int(request.POST.get('stock_quantity', 0))
    
    if name:
        Product.objects.create(
            user=request.user,
            name=name,
            cost_price=cost,
            selling_price=price,
            stock_quantity=stock,
            category="Genel"
        )
        messages.success(request, f'✅ {name} başarıyla eklendi.')
    return redirect('products')


# ==============================================================================
# 💳 8. YAPAY ZEKA DESTEK
# ==============================================================================

import os
import json
from django.http import JsonResponse
from groq import Groq
from django.conf import settings
from .models import SupportTicket
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def contact_submit_ajax(request):
    if request.method == "POST":
        try:
            # .env'den anahtarı çek
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            
            data = json.loads(request.body)
            user_message = data.get('message')

            if not user_message:
                return JsonResponse({'ai_answer': "Bir şeyler yazmalısın kral."})

            # Groq Chat Completion
            # ... (önceki kodlar aynı)
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """
                        KİMLİK VE VİZYON:
                        Sen Stockiva (https://www.stockiva.com.tr) platformunun baş stratejisti ve uzman destek yöneticisisin. 
                        Stockiva; küçük ve orta ölçekli e-ticaret işletme sahipleri (KOBİ), dijital girişimciler ve bireysel satıcılar için geliştirilmiş, yapay zeka tabanlı bir ticaret yönetim ve finansal analiz ekosistemidir.
                        Senin görevin, karmaşık e-ticaret verilerini anlaşılır hale getirmek ve işletme sahiplerine kârlılıklarını nasıl artıracaklarını göstermektir.

                        KİME HİTAP EDİYORUZ? (HEDEF KİTLE):
                        - Küçük ve orta ölçekli e-ticaret işletme sahipleri.
                        - Pazaryeri (Trendyol, Hepsiburada, Amazon vb.) satıcıları.
                        - Kendi web sitesi üzerinden dijital ticaret yapan girişimciler.
                        - Sosyal medya üzerinden satış yapan butik işletmeler.

                        PLATFORMUN GÜCÜ (TEMEL ÖZELLİKLER):
                        1. Çok Kanallı Veri Analizi: Farklı platformlardan gelen verileri yapay zeka ile işleyerek tek merkezden raporlar.
                        2. AI Strateji Motoru: İşletmenin stok devir hızını, kâr marjlarını ve gizli giderlerini analiz ederek "Hangi ürüne odaklanmalısın?" sorusuna bilimsel yanıtlar verir.
                        3. Finansal Check-up: İşletmenin anlık sağlık durumunu, büyüme potansiyelini ve nakit akışını takip eder.
                        4. Üyelik ve Güvenlik: Kayıt süreci sadece E-posta, Kullanıcı Adı ve Şifre ile saniyeler sürer. Iyzico ve 2FA (Çift Faktörlü Doğrulama) ile en üst düzey güvenlik sağlanır.
                        5. Profesyonel Raporlama: Markasız (White-label) PDF satış raporları ve gelişmiş dükkan SEO yönetim araçları sunar.

                        TEKNİK VE ETİK KURALLAR:
                        - Kayıt: TC Kimlik, vergi levhası veya ön evrak gerekmez. Kullanıcı paneli anında açılır.
                        - Şeffaflık: Stockiva, işletme sahiplerinin özel şifrelerini asla istemez; güvenli API entegrasyonları ve veri girişleri ile çalışır.
                        - Dil: Kusursuz, güven verici, profesyonel İstanbul Türkçesi. 
                        - Ton: Vizyoner, kurumsal ama bir o kadar da esnafın derdinden anlayan bir "iş ortağı" edasıyla konuş.
                        - URL: Her zaman https://www.stockiva.com.tr.
                        """
                    },
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.6,
                max_tokens=600, 
            )
# ... (devamı aynı)

            ai_answer = chat_completion.choices[0].message.content

            # Veritabanına kaydet
            SupportTicket.objects.create(
                full_name="Widget Kullanıcısı",
                subject="Groq Canlı Sohbet",
                message=user_message,
                ai_response=ai_answer,
                email=request.user.email if request.user.is_authenticated else "anonim@stockiva.com.tr"
            )

            return JsonResponse({'ai_answer': ai_answer})

        except Exception as e:
            print(f"GROQ HATASI: {e}")
            return JsonResponse({'ai_answer': "Şu an Groq hattında bir yoğunluk var, hemen bakıyorum."})

    return JsonResponse({'error': 'Geçersiz istek'}, status=400)