from rest_framework.permissions import BasePermission

class IsAdminOrSuperuser(BasePermission):
    """
    Allows access only to authenticated users who have is_staff=True or is_superuser=True.
    """
    message = "Ushbu ma'lumotlarga kirish uchun admin huquqi talab qilinadi."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_staff or request.user.is_superuser)
        )
