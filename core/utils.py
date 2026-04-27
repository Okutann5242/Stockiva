"""
core/utils.py — Tekrar kullanılan yardımcı fonksiyonlar.
View'larda kopyala-yapıştır yerine buradan import edilir.
"""

import hmac
import hashlib
import logging
import os

import requests
from django.conf import settings

logger = logging.getLogger('core')


# ==============================================================================
# 🤖 GROQ API YARDIMCISI
# ==============================================================================

def call_groq(prompt: str, temperature: float = 0.7, timeout: int = 15) -> str | None:
    """
    Groq API'ye istek gönderir ve yanıt metnini döner.
    Hata durumunda None döner, exception fırlatmaz.

    Kullanım:
        result = call_groq("Ürünü analiz et: ...")
        if result is None:
            # Hata mesajı göster
    """
    api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
    if not api_key:
        logger.error('GROQ_API_KEY tanımlı değil.')
        return None

    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': temperature,
            },
            timeout=timeout,
        )
        result = response.json()
        if 'choices' in result:
            return result['choices'][0]['message']['content']
        logger.error(f'Groq beklenmeyen yanıt: {result}')
        return None
    except requests.Timeout:
        logger.error('Groq API zaman aşımı.')
        return None
    except Exception as e:
        logger.error(f'Groq API hatası: {e}')
        return None


# ==============================================================================
# 🔐 SHOPIER WEBHOOK İMZA DOĞRULAMA
# ==============================================================================

def verify_shopier_signature(request, secret: str) -> bool:
    """
    Shopier'den gelen webhook isteğinin imzasını doğrular.
    secret: Profile.shopier_webhook_secret (kullanıcıya özel)
    
    Kullanım:
        if not verify_shopier_signature(request, profile.shopier_webhook_secret):
            return HttpResponse(status=403)
    """
    if not secret:
        # Kullanıcı henüz secret girmemişse doğrulamayı atla (uyarı ver)
        logger.warning('Shopier webhook secret girilmemiş — imza doğrulaması atlandı!')
        return True

    signature = request.headers.get('X-Shopier-Signature', '')
    if not signature:
        logger.warning('Webhook isteğinde X-Shopier-Signature header\'ı yok.')
        return False

    expected = hmac.new(
        secret.encode('utf-8'),
        request.body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)

# ==============================================================================
# 🔢 SAYI FORMATLAMA
# ==============================================================================

def safe_float(value, default: float = 0.0) -> float:
    """
    Herhangi bir değeri güvenle float'a çevirir.
    Virgüllü sayıları, None'ı ve boş string'leri handle eder.
    """
    if value is None:
        return default
    try:
        return float(str(value).replace(',', '.').strip())
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    """Herhangi bir değeri güvenle int'e çevirir."""
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default
