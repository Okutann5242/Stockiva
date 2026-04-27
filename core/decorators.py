"""
core/decorators.py — Yetkilendirme dekoratörleri.
"""

import logging
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

logger = logging.getLogger('core')


def pro_required(view_func):
    """
    Sadece PRO üyelere açık view'lar için dekoratör.
    Abonelik süresi dolmuşsa da erişimi keser.

    Kullanım:
        @login_required
        @pro_required
        def ai_shop_analysis(request):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            profile = request.user.profile
            if profile.check_subscription():
                return view_func(request, *args, **kwargs)
        except Exception:
            pass
        messages.warning(
            request,
            '🔒 Bu özellik yalnızca PRO üyelere açıktır. '
            'Üyeliğinizi yükseltmek için Ayarlar sayfasını ziyaret edin.'
        )
        return redirect('settings')
    return _wrapped_view


def admin_required(view_func):
    """
    Sadece is_admin=True olan kullanıcılara açık view'lar için.

    Kullanım:
        @login_required
        @admin_required
        def admin_panel(request):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            if request.user.profile.is_admin:
                return view_func(request, *args, **kwargs)
        except Exception:
            pass
        logger.warning(f'Yetkisiz admin erişim girişimi: {request.user.username}')
        messages.error(request, '⛔ Bu sayfaya erişim yetkiniz yok.')
        return redirect('dashboard')
    return _wrapped_view
