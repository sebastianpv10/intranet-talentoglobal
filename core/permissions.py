from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Empleado

RH, IT, FIN, OPS = Empleado.ROL_RH, Empleado.ROL_IT, Empleado.ROL_FINANZAS, Empleado.ROL_OPERACIONES
TODOS_LIDERES = (RH, IT, FIN, OPS)


def rol_de(user):
    """Rol efectivo del usuario (el superusuario siempre es ADMIN)."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return Empleado.ROL_ADMIN
    emp = getattr(user, "empleado", None)
    if emp and emp.activo:
        return emp.rol
    return None


def tiene_acceso(user, roles):
    """RBAC: ADMIN accede a todo; el resto solo a los roles indicados."""
    rol = rol_de(user)
    return rol == Empleado.ROL_ADMIN or (rol is not None and rol in roles)


def usuario_es_admin(user):
    """Acceso al panel de Gestión Humana (RH + superadmin)."""
    return tiene_acceso(user, (RH,))


def rol_required(*roles):
    """Decorador RBAC para vistas basadas en función."""

    def deco(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            if not tiene_acceso(request.user, roles):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return _wrapped

    return deco


admin_required = rol_required(RH)


class RolRequiredMixin(LoginRequiredMixin):
    """Mixin RBAC para vistas basadas en clase. Defina `roles = (...)`."""

    roles = (RH,)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not tiene_acceso(request.user, self.roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(RolRequiredMixin):
    roles = (RH,)
