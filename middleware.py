from django.shortcuts import render
from django.http import JsonResponse
from .models import SystemSetting

class MaintenanceModeMiddleware:
    """
    Middleware that intercepts all client requests when maintenance mode is active.
    Allows administrators and panel routes to proceed unhindered.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if (
            path.startswith('/panel') or
            path.startswith('/admin') or
            path.startswith('/api/admin') or
            path.startswith('/static/') or
            path.startswith('/media/')
        ):
            return self.get_response(request)

        try:
            settings_obj = SystemSetting.get_settings()
            if settings_obj.maintenance_mode:
                if hasattr(request, 'user') and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
                    return self.get_response(request)

                auth_header = request.META.get('HTTP_AUTHORIZATION', '')
                if auth_header.startswith('Bearer '):
                    try:
                        from rest_framework_simplejwt.tokens import AccessToken
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        token_str = auth_header.split(' ')[1]
                        token = AccessToken(token_str)
                        user_id = token.payload.get('user_id')
                        if user_id:
                            u = User.objects.filter(id=user_id).first()
                            if u and (u.is_staff or u.is_superuser):
                                return self.get_response(request)
                    except Exception:
                        pass

                if path.startswith('/api/'):
                    return JsonResponse({
                        "error": "Serverda texnik ta'mirlash ishlari olib borilmoqda. Tizim tez orada qayta ishga tushadi.",
                        "maintenance": True
                    }, status=503)

                return render(request, 'maintenance.html', {
                    "announcement": settings_obj.announcement_banner
                }, status=503)
        except Exception:
            pass

        return self.get_response(request)
