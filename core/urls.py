from django.contrib.auth import views as auth_views
from django.urls import path

from . import views as v

urlpatterns = [
    # Autenticación y navegación central
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", v.dashboard, name="dashboard"),

    # Autogestión común de colaborador
    path("perfil/", v.mi_perfil, name="mi_perfil"),
    path("firma/", v.firma_x, name="firma_x"),
    path("certificado/", v.certificado_laboral, name="certificado"),
    path("certificado/<int:pk>/", v.certificado_laboral, name="certificado_empleado"),

    # Noticias Corporativas
    path("noticias/", v.NoticiaList.as_view(), name="noticia_list"),
    path("noticias/nueva/", v.noticia_crear, name="noticia_crear"),
    path("noticias/<int:pk>/", v.noticia_detalle, name="noticia_detalle"),

    # Cursos y Capacitación
    path("cursos/", v.CursoList.as_view(), name="curso_list"),
    path("cursos/nuevo/", v.CursoCreate.as_view(), name="curso_create"),
    path("cursos/<int:pk>/", v.curso_detalle, name="curso_detalle"),
    path("cursos/<int:pk>/estado/<str:estado>/", v.curso_cambiar_estado, name="curso_estado"),

    # Módulo A: Talento Humano / Recursos Humanos
    path("empleados/", v.EmpleadoList.as_view(), name="empleado_list"),
    path("empleados/nuevo/", v.EmpleadoCreate.as_view(), name="empleado_create"),
    path("empleados/<int:pk>/editar/", v.EmpleadoUpdate.as_view(), name="empleado_update"),
    path("empleados/<int:pk>/estado/", v.empleado_toggle, name="empleado_toggle"),
    path("empleados/<int:pk>/reset-password/", v.empleado_reset_password, name="empleado_reset"),

    path("sedes/", v.SedeList.as_view(), name="sede_list"),
    path("sedes/nueva/", v.SedeCreate.as_view(), name="sede_create"),
    path("sedes/<int:pk>/editar/", v.SedeUpdate.as_view(), name="sede_update"),
    path("sedes/<int:pk>/eliminar/", v.SedeDelete.as_view(), name="sede_delete"),

    path("departamentos/", v.DepartamentoList.as_view(), name="departamento_list"),
    path("departamentos/nuevo/", v.DepartamentoCreate.as_view(), name="departamento_create"),
    path("departamentos/<int:pk>/editar/", v.DepartamentoUpdate.as_view(), name="departamento_update"),
    path("departamentos/<int:pk>/eliminar/", v.DepartamentoDelete.as_view(), name="departamento_delete"),

    path("vacaciones/solicitar/", v.vacaciones_solicitar, name="vacaciones_solicitar"),
    path("vacaciones/mis-solicitudes/", v.vacaciones_mis_solicitudes, name="vacaciones_mis_solicitudes"),
    path("vacaciones/gestion/", v.vacaciones_panel_aprobacion, name="vacaciones_panel_aprobacion"),
    path("vacaciones/<int:pk>/<str:accion>/", v.vacaciones_resolver, name="vacaciones_resolver"),

    path("nomina/", v.NominaList.as_view(), name="nomina_list"),
    path("nomina/generar/", v.nomina_crear, name="nomina_crear"),
    path("nomina/exportar/", v.exportar_excel, name="exportar_excel"),
    path("nomina/<int:pk>/", v.nomina_detalle, name="nomina_detalle"),
    path("nomina/<int:pk>/eliminar/", v.nomina_eliminar, name="nomina_eliminar"),

    # Módulo B: Tecnología e Infraestructura (IT Support)
    path("soporte/tickets/nuevo/", v.ticket_crear, name="ticket_crear"),
    path("soporte/tickets/mis-tickets/", v.ticket_mis_tickets, name="ticket_mis_tickets"),
    path("soporte/tickets/gestion/", v.ticket_panel_it, name="ticket_panel_it"),
    path("soporte/tickets/<int:pk>/", v.ticket_detalle, name="ticket_detalle"),

    path("tecnologia/activos/", v.ActivoList.as_view(), name="activo_list"),
    path("tecnologia/activos/nuevo/", v.ActivoCreate.as_view(), name="activo_create"),
    path("tecnologia/activos/<int:pk>/editar/", v.ActivoUpdate.as_view(), name="activo_update"),
    path("tecnologia/activos/<int:pk>/eliminar/", v.ActivoDelete.as_view(), name="activo_delete"),

    # Módulo C: Finanzas y Contabilidad
    path("finanzas/anticipos/solicitar/", v.anticipo_solicitar, name="anticipo_solicitar"),
    path("finanzas/anticipos/mis-solicitudes/", v.anticipo_mis_solicitudes, name="anticipo_mis_solicitudes"),
    path("finanzas/anticipos/gestion/", v.anticipo_panel_finanzas, name="anticipo_panel_finanzas"),
    path("finanzas/anticipos/<int:pk>/<str:accion>/", v.anticipo_resolver, name="anticipo_resolver"),

    # Módulo D: Operaciones y Logística
    path("operaciones/reservas/", v.reserva_calendario, name="reserva_calendario"),
    path("operaciones/reservas/nueva/", v.reserva_crear, name="reserva_crear"),
    path("operaciones/reservas/<int:pk>/cancelar/", v.reserva_cancelar, name="reserva_cancelar"),

    path("operaciones/espacios/", v.EspacioList.as_view(), name="espacio_list"),
    path("operaciones/espacios/nuevo/", v.EspacioCreate.as_view(), name="espacio_create"),
    path("operaciones/espacios/<int:pk>/editar/", v.EspacioUpdate.as_view(), name="espacio_update"),
]
