from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .forms import (
    ActivoTecnologicoForm,
    CursoCapacitacionForm,
    DepartamentoForm,
    EmpleadoForm,
    EspacioForm,
    ExtractoNominaForm,
    NoticiaCorporativaForm,
    PerfilAutogestionForm,
    ReservaEspacioForm,
    SedeForm,
    SolicitudAnticipoForm,
    SolicitudVacacionesForm,
    TicketAtencionForm,
    TicketSoporteForm,
)
from .models import (
    ActivoTecnologico,
    AsignacionCurso,
    CursoCapacitacion,
    Departamento,
    Empleado,
    Espacio,
    ExtractoNomina,
    NoticiaCorporativa,
    ReservaEspacio,
    Sede,
    SolicitudAnticipo,
    SolicitudVacaciones,
    TicketSoporte,
)
from .permissions import (
    FIN,
    IT,
    OPS,
    RH,
    TODOS_LIDERES,
    AdminRequiredMixin,
    RolRequiredMixin,
    admin_required,
    rol_required,
    tiene_acceso,
    usuario_es_admin,
)

MAX_FIRMA_BYTES = 400_000


# ==============================================================================
# DASHBOARD PRINCIPAL Y NOTICIAS
# ==============================================================================
@login_required
def dashboard(request):
    empleado = getattr(request.user, "empleado", None)
    ctx = {"empleado": empleado}

    # Feed de Noticias Corporativas
    noticias = NoticiaCorporativa.objects.filter(publicada=True).select_related("autor__user")[:6]
    ctx["noticias"] = noticias

    # Cursos asignados al colaborador
    if empleado:
        mis_cursos = AsignacionCurso.objects.filter(empleado=empleado).select_related("curso")
        ctx["mis_cursos"] = mis_cursos
        ctx["cursos_pendientes"] = mis_cursos.filter(
            estado__in=[AsignacionCurso.PENDIENTE, AsignacionCurso.EN_CURSO]
        ).count()
        ctx["mis_colillas"] = empleado.extractos.all()[:3]
        ctx["mis_tickets"] = empleado.tickets.all()[:3]
        ctx["mis_activos"] = empleado.activos.all()

    # Métricas y resúmenes para líderes y administradores
    if tiene_acceso(request.user, TODOS_LIDERES):
        hoy = date.today().replace(day=1)
        nomina_mes = ExtractoNomina.objects.filter(periodo=hoy)
        tot_nomina = nomina_mes.aggregate(
            dev=Sum("total_devengado"), ded=Sum("total_deducciones"), neto=Sum("neto_pagar")
        )
        ctx.update(
            total_empleados=Empleado.objects.filter(activo=True).count(),
            total_sedes=Sede.objects.count(),
            total_deptos=Departamento.objects.count(),
            nomina_devengado=tot_nomina["dev"] or 0,
            nomina_deducciones=tot_nomina["ded"] or 0,
            nomina_neto=tot_nomina["neto"] or 0,
            colillas_mes=nomina_mes.count(),
            vacaciones_pendientes=SolicitudVacaciones.objects.filter(estado=SolicitudVacaciones.PENDIENTE).count(),
            anticipos_pendientes=SolicitudAnticipo.objects.filter(estado=SolicitudAnticipo.PENDIENTE).count(),
            tickets_abiertos=TicketSoporte.objects.filter(estado__in=["ABIERTO", "EN_PROCESO"]).count(),
            por_depto=Departamento.objects.annotate(
                n=Count("empleados", filter=Q(empleados__activo=True))
            ).order_by("-n"),
            ultimos_empleados=Empleado.objects.select_related("user", "sede", "departamento").order_by("-id")[:5],
        )

    return render(request, "core/dashboard.html", ctx)


# ---------------------------------------------------- Noticias
class NoticiaList(ListView):
    model = NoticiaCorporativa
    template_name = "core/noticia_list.html"
    context_object_name = "noticias"
    paginate_by = 10

    def get_queryset(self):
        return NoticiaCorporativa.objects.filter(publicada=True).select_related("autor__user")


@rol_required(*TODOS_LIDERES)
def noticia_crear(request):
    form = NoticiaCorporativaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        noticia = form.save(commit=False)
        noticia.autor = getattr(request.user, "empleado", None)
        noticia.save()
        messages.success(request, "Noticia corporativa publicada exitosamente.")
        return redirect("dashboard")
    return render(request, "core/form.html", {
        "form": form,
        "titulo": "Publicar Noticia Corporativa",
        "volver": reverse_lazy("dashboard"),
    })


def noticia_detalle(request, pk):
    noticia = get_object_or_404(NoticiaCorporativa.objects.select_related("autor__user"), pk=pk)
    return render(request, "core/noticia_detalle.html", {"noticia": noticia})


# ==============================================================================
# MÓDULO A: RECURSOS HUMANOS (TALENTO HUMANO)
# ==============================================================================
@login_required
def mi_perfil(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    form = PerfilAutogestionForm(request.POST or None, instance=empleado)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos personales actualizados correctamente.")
        return redirect("mi_perfil")
    return render(request, "core/perfil.html", {"form": form, "empleado": empleado})


@login_required
def firma_x(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    if request.method == "POST":
        data = request.POST.get("firma", "")
        if request.POST.get("accion") == "borrar":
            empleado.guardar_firma("")
            messages.success(request, "Firma X eliminada correctamente.")
        elif data.startswith("data:image/png;base64,") and len(data) <= MAX_FIRMA_BYTES:
            empleado.guardar_firma(data)
            messages.success(request, "Firma digital X guardada y vinculada a sus certificados laborales.")
        else:
            messages.error(request, "Firma no válida o excede el tamaño permitido.")
        return redirect("firma_x")
    return render(request, "core/firma.html", {"empleado": empleado})


# ---------------------------------------------------- Vacaciones y Permisos
@login_required
def vacaciones_solicitar(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    form = SolicitudVacacionesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sol = form.save(commit=False)
        sol.empleado = empleado
        sol.save()
        messages.success(request, "Solicitud de vacaciones/permiso radicada ante Gestión Humana.")
        return redirect("vacaciones_mis_solicitudes")
    return render(request, "core/form.html", {
        "form": form,
        "titulo": "Solicitar Vacaciones / Permiso",
        "nota": "La solicitud será evaluada por el área de Recursos Humanos.",
        "volver": reverse_lazy("vacaciones_mis_solicitudes"),
    })


@login_required
def vacaciones_mis_solicitudes(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    solicitudes = empleado.vacaciones.all()
    return render(request, "core/vacaciones_lista.html", {
        "solicitudes": solicitudes,
        "es_gestion": False,
    })


@rol_required(RH)
def vacaciones_panel_aprobacion(request):
    solicitudes = SolicitudVacaciones.objects.select_related("empleado__user", "empleado__departamento").order_by("-creado")
    return render(request, "core/vacaciones_lista.html", {
        "solicitudes": solicitudes,
        "es_gestion": True,
    })


@rol_required(RH)
def vacaciones_resolver(request, pk, accion):
    if request.method == "POST":
        sol = get_object_or_404(SolicitudVacaciones, pk=pk)
        revisor = getattr(request.user, "empleado", None)
        comentario = request.POST.get("comentario", "")
        aprobar = (accion == "aprobar")
        sol.resolver(aprobar=aprobar, revisor=revisor, comentario=comentario)
        messages.success(request, f"Solicitud #{sol.pk} marcada como {'Aprobada' if aprobar else 'Rechazada'}.")
    return redirect("vacaciones_panel_aprobacion")


# ---------------------------------------------------- Empleados (CRUD RH)
class EmpleadoList(RolRequiredMixin, ListView):
    roles = (RH,)
    template_name = "core/empleado_list.html"
    context_object_name = "empleados"
    paginate_by = 15

    def get_queryset(self):
        qs = Empleado.objects.select_related("user", "sede", "departamento")
        g = self.request.GET
        if g.get("q"):
            q = g["q"]
            qs = qs.filter(
                Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(documento__icontains=q)
                | Q(cargo__icontains=q)
            )
        if g.get("sede"):
            qs = qs.filter(sede_id=g["sede"])
        if g.get("departamento"):
            qs = qs.filter(departamento_id=g["departamento"])
        if g.get("estado") in ("1", "0"):
            qs = qs.filter(activo=(g["estado"] == "1"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sedes"] = Sede.objects.all()
        ctx["departamentos"] = Departamento.objects.all()
        ctx["f"] = self.request.GET
        qd = self.request.GET.copy()
        qd.pop("page", None)
        ctx["qs"] = qd.urlencode()
        return ctx


class EmpleadoCreate(RolRequiredMixin, CreateView):
    roles = (RH,)
    model = Empleado
    form_class = EmpleadoForm
    template_name = "core/form.html"
    success_url = reverse_lazy("empleado_list")
    extra_context = {
        "titulo": "Registrar Nuevo Colaborador",
        "nota": "El sistema creará el usuario con el número de documento y la contraseña predeterminada «admin».",
        "volver": reverse_lazy("empleado_list"),
    }

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(
            self.request,
            f"Colaborador {self.object.nombre_completo} creado con éxito. Usuario: {self.object.documento} / Contraseña: admin",
        )
        return r


class EmpleadoUpdate(RolRequiredMixin, UpdateView):
    roles = (RH,)
    model = Empleado
    form_class = EmpleadoForm
    template_name = "core/form.html"
    success_url = reverse_lazy("empleado_list")
    extra_context = {"titulo": "Editar Datos del Colaborador", "volver": reverse_lazy("empleado_list")}

    def form_valid(self, form):
        messages.success(self.request, "Información del colaborador actualizada.")
        return super().form_valid(form)


@rol_required(RH)
def empleado_toggle(request, pk):
    if request.method != "POST":
        return redirect("empleado_list")
    emp = get_object_or_404(Empleado, pk=pk)
    if emp.user_id == request.user.id:
        messages.error(request, "No puede desactivar su propia cuenta de acceso.")
        return redirect("empleado_list")
    emp.activo = not emp.activo
    emp.save(update_fields=["activo"])
    emp.user.is_active = emp.activo
    emp.user.save(update_fields=["is_active"])
    messages.success(request, f"Estado de {emp.nombre_completo} actualizado a {'Activo' if emp.activo else 'Inactivo'}.")
    return redirect("empleado_list")


@rol_required(RH)
def empleado_reset_password(request, pk):
    if request.method == "POST":
        emp = get_object_or_404(Empleado, pk=pk)
        emp.user.set_password(settings.PASSWORD_PREDETERMINADA)
        emp.user.save()
        messages.success(request, f"Contraseña de {emp.nombre_completo} restablecida a «admin».")
    return redirect("empleado_list")


# ---------------------------------------------------- Sedes y Departamentos
class _CrudMixin(RolRequiredMixin):
    roles = (RH,)
    template_name = "core/form.html"
    url_lista = ""

    @property
    def success_url(self):
        return reverse_lazy(self.url_lista)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["volver"] = self.success_url
        return ctx


class SedeList(RolRequiredMixin, ListView):
    roles = (RH,)
    model = Sede
    template_name = "core/sede_list.html"
    context_object_name = "sedes"

    def get_queryset(self):
        return Sede.objects.annotate(n=Count("empleados"))


class SedeCreate(_CrudMixin, CreateView):
    model, form_class, url_lista = Sede, SedeForm, "sede_list"
    extra_context = {"titulo": "Nueva Sede Corporativa"}


class SedeUpdate(_CrudMixin, UpdateView):
    model, form_class, url_lista = Sede, SedeForm, "sede_list"
    extra_context = {"titulo": "Editar Sede Corporativa"}


class DepartamentoList(RolRequiredMixin, ListView):
    roles = (RH,)
    model = Departamento
    template_name = "core/departamento_list.html"
    context_object_name = "departamentos"

    def get_queryset(self):
        return Departamento.objects.annotate(n=Count("empleados"))


class DepartamentoCreate(_CrudMixin, CreateView):
    model, form_class, url_lista = Departamento, DepartamentoForm, "departamento_list"
    extra_context = {"titulo": "Nuevo Departamento"}


class DepartamentoUpdate(_CrudMixin, UpdateView):
    model, form_class, url_lista = Departamento, DepartamentoForm, "departamento_list"
    extra_context = {"titulo": "Editar Departamento"}


class _BorrarMixin(RolRequiredMixin, DeleteView):
    roles = (RH,)
    template_name = "core/confirm_delete.html"
    url_lista = ""

    @property
    def success_url(self):
        return reverse_lazy(self.url_lista)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["volver"] = self.success_url
        return ctx

    def form_valid(self, form):
        try:
            r = super().form_valid(form)
            messages.success(self.request, "Registro eliminado exitosamente.")
            return r
        except ProtectedError:
            messages.error(self.request, "No se puede eliminar: existen colaboradores o recursos vinculados.")
            return redirect(self.success_url)


class SedeDelete(_BorrarMixin):
    model, url_lista = Sede, "sede_list"


class DepartamentoDelete(_BorrarMixin):
    model, url_lista = Departamento, "departamento_list"


# ---------------------------------------------------- Nómina y Colillas
class NominaList(RolRequiredMixin, ListView):
    roles = (RH, FIN)
    template_name = "core/nomina_list.html"
    context_object_name = "extractos"
    paginate_by = 20

    def get_queryset(self):
        qs = ExtractoNomina.objects.select_related("empleado__user", "empleado__departamento")
        p = self.request.GET.get("periodo")
        if p:
            try:
                y, m = map(int, p.split("-"))
                qs = qs.filter(periodo=date(y, m, 1))
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["totales"] = self.get_queryset().aggregate(
            dev=Sum("total_devengado"), ded=Sum("total_deducciones"), neto=Sum("neto_pagar")
        )
        ctx["periodo"] = self.request.GET.get("periodo", "")
        return ctx


@rol_required(RH, FIN)
def nomina_crear(request):
    form = ExtractoNominaForm(request.POST or None, initial={"periodo": date.today().replace(day=1)})
    if request.method == "POST" and form.is_valid():
        extracto = form.save()
        messages.success(request, "Colilla de pago generada con deducciones automáticas (Salud 4%, Pensión 4%).")
        return redirect("nomina_detalle", pk=extracto.pk)
    salarios = {e.pk: str(e.salario_base) for e in Empleado.objects.filter(activo=True)}
    return render(request, "core/nomina_form.html", {"form": form, "salarios": salarios})


@login_required
def nomina_detalle(request, pk):
    extracto = get_object_or_404(ExtractoNomina.objects.select_related("empleado__user", "empleado__sede", "empleado__departamento"), pk=pk)
    if not tiene_acceso(request.user, (RH, FIN)) and extracto.empleado.user_id != request.user.id:
        raise PermissionDenied
    return render(request, "core/nomina_detalle.html", {"e": extracto})


@rol_required(RH)
def nomina_eliminar(request, pk):
    if request.method == "POST":
        get_object_or_404(ExtractoNomina, pk=pk).delete()
        messages.success(request, "Colilla de pago eliminada.")
    return redirect("nomina_list")


# ---------------------------------------------------- Certificados Laborales
@login_required
def certificado_laboral(request, pk=None):
    if pk and tiene_acceso(request.user, (RH,)):
        empleado = get_object_or_404(Empleado, pk=pk)
    else:
        empleado = get_object_or_404(Empleado, user=request.user)

    return render(request, "core/certificado_laboral.html", {
        "empleado": empleado,
        "hoy": date.today(),
    })


# ---------------------------------------------------- Exportación a Excel (.xlsx)
@rol_required(RH, FIN)
def exportar_excel(request):
    """Genera y descarga el consolidado financiero y de personal en formato .xlsx."""
    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="4F46E5")
    head_font = Font(bold=True, color="FFFFFF")

    def formatear_hoja(ws, titulo, headers, filas, money_cols=()):
        ws.title = titulo
        ws.append(headers)
        for c in ws[1]:
            c.fill, c.font = head_fill, head_font
            c.alignment = Alignment(horizontal="center", vertical="center")
        for f in filas:
            ws.append(f)
        for col in money_cols:
            for cell in ws[get_column_letter(col)][1:]:
                cell.number_format = '"$"#,##0'
        for i, h in enumerate(headers, 1):
            ancho = max([len(str(h))] + [len(str(r[i - 1])) for r in filas] or [12])
            ws.column_dimensions[get_column_letter(i)].width = min(ancho + 4, 45)
        ws.freeze_panes = "A2"

    # Hoja 1: Empleados
    emps = Empleado.objects.select_related("user", "sede", "departamento")
    formatear_hoja(
        wb.active,
        "Colaboradores",
        [
            "Documento", "Nombre Completo", "Correo Electrónico", "Teléfono", "Cargo",
            "Departamento", "Sede", "Tipo Contrato", "Fecha Ingreso", "Salario Base",
            "Rol", "Estado", "Firma X",
        ],
        [
            [
                e.documento, e.nombre_completo, e.user.email, e.telefono, e.cargo,
                e.departamento.nombre, e.sede.nombre, e.get_tipo_contrato_display(),
                e.fecha_ingreso, float(e.salario_base), e.get_rol_display(),
                "Activo" if e.activo else "Inactivo",
                "Registrada" if e.firma_x else "Pendiente",
            ]
            for e in emps
        ],
        money_cols=(10,),
    )

    # Hoja 2: Nómina
    ext = ExtractoNomina.objects.select_related("empleado__user", "empleado__departamento")
    filas_nom = [
        [
            x.periodo.strftime("%Y-%m"), x.empleado.documento, x.empleado.nombre_completo,
            x.empleado.departamento.nombre, float(x.devengado_base), float(x.bonificaciones),
            float(x.total_devengado), float(x.deduccion_salud), float(x.deduccion_pension),
            float(x.otras_deducciones), float(x.total_deducciones), float(x.neto_pagar),
        ]
        for x in ext
    ]
    ws_nom = wb.create_sheet()
    formatear_hoja(
        ws_nom,
        "Consolidado Nómina",
        [
            "Periodo", "Documento", "Colaborador", "Departamento", "Devengado Base",
            "Bonificaciones", "Total Devengado", "Salud (4%)", "Pensión (4%)",
            "Otras Deducciones", "Total Deducciones", "Neto a Pagar",
        ],
        filas_nom,
        money_cols=range(5, 13),
    )
    if filas_nom:
        n = len(filas_nom) + 2
        ws_nom.append(["TOTAL", "", "", ""] + [f"=SUM({get_column_letter(c)}2:{get_column_letter(c)}{n - 1})" for c in range(5, 13)])
        for c in ws_nom[n]:
            c.font = Font(bold=True)
            c.number_format = '"$"#,##0'

    # Hoja 3: Sedes y Departamentos
    ws_sedes = wb.create_sheet()
    formatear_hoja(
        ws_sedes,
        "Sedes y Sucursales",
        ["Sede", "Ciudad", "Dirección", "Teléfono", "Colaboradores Asignados"],
        [[s.nombre, s.ciudad, s.direccion, s.telefono, s.n] for s in Sede.objects.annotate(n=Count("empleados"))],
    )

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="TalentoGlobal_Reporte_General_{date.today():%Y%m%d}.xlsx"'
    wb.save(resp)
    return resp


# ==============================================================================
# MÓDULO B: TECNOLOGÍA E INFRAESTRUCTURA (IT SUPPORT)
# ==============================================================================
@login_required
def ticket_crear(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    form = TicketSoporteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.solicitante = empleado
        ticket.save()
        messages.success(request, f"Ticket de soporte #{ticket.pk} creado con éxito. El equipo de IT lo atenderá pronto.")
        return redirect("ticket_mis_tickets")
    return render(request, "core/form.html", {
        "form": form,
        "titulo": "Nuevo Requerimiento de Soporte Técnico",
        "nota": "Describa con claridad la falla de hardware, software o acceso para priorizar la atención.",
        "volver": reverse_lazy("ticket_mis_tickets"),
    })


@login_required
def ticket_mis_tickets(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    tickets = empleado.tickets.all()
    return render(request, "core/ticket_lista.html", {"tickets": tickets, "es_gestion_it": False})


@rol_required(IT)
def ticket_panel_it(request):
    tickets = TicketSoporte.objects.select_related("solicitante__user", "asignado_a__user").order_by("-creado")
    return render(request, "core/ticket_lista.html", {"tickets": tickets, "es_gestion_it": True})


@login_required
def ticket_detalle(request, pk):
    ticket = get_object_or_404(TicketSoporte.objects.select_related("solicitante__user", "asignado_a__user"), pk=pk)
    es_it = tiene_acceso(request.user, (IT,))
    if not es_it and ticket.solicitante.user_id != request.user.id:
        raise PermissionDenied

    form = TicketAtencionForm(request.POST or None, instance=ticket) if es_it else None
    if request.method == "POST" and es_it and form and form.is_valid():
        form.save()
        messages.success(request, f"Ticket #{ticket.pk} actualizado por el equipo de IT.")
        return redirect("ticket_panel_it")

    return render(request, "core/ticket_detalle.html", {"ticket": ticket, "form": form, "es_it": es_it})


# ---------------------------------------------------- Inventario de Activos IT
class ActivoList(RolRequiredMixin, ListView):
    roles = (IT,)
    model = ActivoTecnologico
    template_name = "core/activo_list.html"
    context_object_name = "activos"

    def get_queryset(self):
        qs = ActivoTecnologico.objects.select_related("asignado_a__user")
        tipo = self.request.GET.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs


class ActivoCreate(RolRequiredMixin, CreateView):
    roles = (IT,)
    model = ActivoTecnologico
    form_class = ActivoTecnologicoForm
    template_name = "core/form.html"
    success_url = reverse_lazy("activo_list")
    extra_context = {"titulo": "Registrar Activo Tecnológico", "volver": reverse_lazy("activo_list")}


class ActivoUpdate(RolRequiredMixin, UpdateView):
    roles = (IT,)
    model = ActivoTecnologico
    form_class = ActivoTecnologicoForm
    template_name = "core/form.html"
    success_url = reverse_lazy("activo_list")
    extra_context = {"titulo": "Editar Activo Tecnológico", "volver": reverse_lazy("activo_list")}


class ActivoDelete(_BorrarMixin):
    roles = (IT,)
    model = ActivoTecnologico
    url_lista = "activo_list"


# ==============================================================================
# MÓDULO C: FINANZAS Y CONTABILIDAD
# ==============================================================================
@login_required
def anticipo_solicitar(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    form = SolicitudAnticipoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ant = form.save(commit=False)
        ant.empleado = empleado
        ant.save()
        messages.success(request, "Solicitud de anticipo/préstamo radicada exitosamente.")
        return redirect("anticipo_mis_solicitudes")
    return render(request, "core/form.html", {
        "form": form,
        "titulo": "Solicitud de Anticipo / Préstamo de Nómina",
        "nota": "El área financiera evaluará su cupo y condiciones de desembolso.",
        "volver": reverse_lazy("anticipo_mis_solicitudes"),
    })


@login_required
def anticipo_mis_solicitudes(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    solicitudes = empleado.anticipos.all()
    return render(request, "core/anticipo_lista.html", {"solicitudes": solicitudes, "es_gestion_fin": False})


@rol_required(FIN)
def anticipo_panel_finanzas(request):
    solicitudes = SolicitudAnticipo.objects.select_related("empleado__user", "empleado__departamento").order_by("-creado")
    return render(request, "core/anticipo_lista.html", {"solicitudes": solicitudes, "es_gestion_fin": True})


@rol_required(FIN)
def anticipo_resolver(request, pk, accion):
    if request.method == "POST":
        sol = get_object_or_404(SolicitudAnticipo, pk=pk)
        revisor = getattr(request.user, "empleado", None)
        comentario = request.POST.get("comentario", "")
        aprobar = (accion == "aprobar")
        sol.resolver(aprobar=aprobar, revisor=revisor, comentario=comentario)
        messages.success(request, f"Anticipo #{sol.pk} marcado como {'Aprobado' if aprobar else 'Rechazada'}.")
    return redirect("anticipo_panel_finanzas")


# ==============================================================================
# MÓDULO D: OPERACIONES Y LOGÍSTICA (RESERVA DE ESPACIOS)
# ==============================================================================
@login_required
def reserva_calendario(request):
    espacios = Espacio.objects.filter(activo=True).select_related("sede")
    hoy = date.today()
    reservas = ReservaEspacio.objects.filter(fecha__gte=hoy, cancelada=False).select_related("espacio", "empleado__user")
    return render(request, "core/reserva_calendario.html", {"espacios": espacios, "reservas": reservas, "hoy": hoy})


@login_required
def reserva_crear(request):
    empleado = get_object_or_404(Empleado, user=request.user)
    form = ReservaEspacioForm(request.POST or None, initial={"fecha": date.today()})
    if request.method == "POST" and form.is_valid():
        res = form.save(commit=False)
        res.empleado = empleado
        res.save()
        messages.success(request, f"Espacio «{res.espacio.nombre}» reservado con éxito para el {res.fecha}.")
        return redirect("reserva_calendario")
    return render(request, "core/form.html", {
        "form": form,
        "titulo": "Reservar Sala o Recurso Audiovisual",
        "nota": "El sistema valida automáticamente que no existan traslapes ni choques de horario.",
        "volver": reverse_lazy("reserva_calendario"),
    })


@login_required
def reserva_cancelar(request, pk):
    if request.method == "POST":
        res = get_object_or_404(ReservaEspacio, pk=pk)
        if not tiene_acceso(request.user, (OPS,)) and res.empleado.user_id != request.user.id:
            raise PermissionDenied
        res.cancelada = True
        res.save(update_fields=["cancelada"])
        messages.success(request, "Reserva cancelada correctamente.")
    return redirect("reserva_calendario")


# ---------------------------------------------------- CRUD Espacios (Líder OPS)
class EspacioList(RolRequiredMixin, ListView):
    roles = (OPS,)
    model = Espacio
    template_name = "core/espacio_list.html"
    context_object_name = "espacios"


class EspacioCreate(RolRequiredMixin, CreateView):
    roles = (OPS,)
    model = Espacio
    form_class = EspacioForm
    template_name = "core/form.html"
    success_url = reverse_lazy("espacio_list")
    extra_context = {"titulo": "Nuevo Espacio / Recurso", "volver": reverse_lazy("espacio_list")}


class EspacioUpdate(RolRequiredMixin, UpdateView):
    roles = (OPS,)
    model = Espacio
    form_class = EspacioForm
    template_name = "core/form.html"
    success_url = reverse_lazy("espacio_list")
    extra_context = {"titulo": "Editar Espacio / Recurso", "volver": reverse_lazy("espacio_list")}


# ==============================================================================
# MÓDULO DE CURSOS Y CAPACITACIÓN CORPORATIVA
# ==============================================================================
@login_required
def curso_detalle(request, pk):
    curso = get_object_or_404(CursoCapacitacion, pk=pk)
    empleado = getattr(request.user, "empleado", None)
    asignacion = None
    if empleado:
        asignacion, _ = AsignacionCurso.objects.get_or_create(curso=curso, empleado=empleado)
    return render(request, "core/curso_detalle.html", {"curso": curso, "asignacion": asignacion})


@login_required
def curso_cambiar_estado(request, pk, estado):
    if request.method == "POST":
        empleado = get_object_or_404(Empleado, user=request.user)
        curso = get_object_or_404(CursoCapacitacion, pk=pk)
        asig, _ = AsignacionCurso.objects.get_or_create(curso=curso, empleado=empleado)
        if estado in [AsignacionCurso.EN_CURSO, AsignacionCurso.COMPLETADO]:
            asig.estado = estado
            if estado == AsignacionCurso.COMPLETADO:
                asig.completado = timezone.now()
            asig.save()
            messages.success(request, f"Progreso actualizado: {asig.get_estado_display()}.")
    return redirect("curso_detalle", pk=pk)


class CursoList(RolRequiredMixin, ListView):
    roles = (RH,)
    model = CursoCapacitacion
    template_name = "core/curso_list.html"
    context_object_name = "cursos"


class CursoCreate(RolRequiredMixin, CreateView):
    roles = (RH,)
    model = CursoCapacitacion
    form_class = CursoCapacitacionForm
    template_name = "core/form.html"
    success_url = reverse_lazy("curso_list")
    extra_context = {"titulo": "Crear Curso de Capacitación", "volver": reverse_lazy("curso_list")}
