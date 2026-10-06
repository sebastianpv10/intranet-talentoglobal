from django.conf import settings

from .permissions import FIN, IT, OPS, RH, TODOS_LIDERES, tiene_acceso


def empresa(request):
    u = request.user
    ctx = {"EMPRESA": settings.EMPRESA}
    if u.is_authenticated:
        ctx.update(
            es_admin=tiene_acceso(u, (RH,)),  # panel de RH
            es_it=tiene_acceso(u, (IT,)),
            es_fin=tiene_acceso(u, (FIN,)),
            es_ops=tiene_acceso(u, (OPS,)),
            es_lider=tiene_acceso(u, TODOS_LIDERES),
        )
    return ctx
