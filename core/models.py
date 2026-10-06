from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

CENT = Decimal("1")


def _redondear(valor):
    return Decimal(valor).quantize(CENT, rounding=ROUND_HALF_UP)


# ============================================================ Estructura
class Sede(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    ciudad = models.CharField(max_length=80)
    direccion = models.CharField("Dirección", max_length=200, blank=True)
    telefono = models.CharField("Teléfono", max_length=30, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.ciudad})"


class Departamento(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField("Descripción", blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Empleado(models.Model):
    ROL_ADMIN = "ADMIN"
    ROL_RH = "RH"
    ROL_IT = "IT"
    ROL_FINANZAS = "FINANZAS"
    ROL_OPERACIONES = "OPERACIONES"
    ROL_EMPLEADO = "EMPLEADO"
    ROLES = [
        (ROL_ADMIN, "Superadministrador"),
        (ROL_RH, "Líder de Recursos Humanos"),
        (ROL_IT, "Líder de Tecnología (IT)"),
        (ROL_FINANZAS, "Líder Financiero"),
        (ROL_OPERACIONES, "Líder de Operaciones y Logística"),
        (ROL_EMPLEADO, "Colaborador"),
    ]

    CONTRATOS = [
        ("INDEFINIDO", "Término indefinido"),
        ("FIJO", "Término fijo"),
        ("OBRA", "Obra o labor"),
        ("APRENDIZAJE", "Aprendizaje"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="empleado")
    documento = models.CharField("Documento de identidad", max_length=20, unique=True)
    cargo = models.CharField(max_length=120)
    salario_base = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_ingreso = models.DateField()
    tipo_contrato = models.CharField(max_length=20, choices=CONTRATOS, default="INDEFINIDO")
    telefono = models.CharField("Teléfono", max_length=30, blank=True)
    direccion = models.CharField("Dirección", max_length=200, blank=True)
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="empleados")
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="empleados"
    )
    rol = models.CharField(max_length=12, choices=ROLES, default=ROL_EMPLEADO)
    activo = models.BooleanField(default=True)
    # Firma X: imagen PNG (data URL base64) del trazo dibujado o rúbrica elegida.
    firma_x = models.TextField("Firma X", blank=True)
    firma_actualizada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return self.user.get_full_name() or self.user.username

    @property
    def es_admin(self):
        return self.rol == self.ROL_ADMIN or self.user.is_superuser

    @property
    def es_lider(self):
        return self.rol != self.ROL_EMPLEADO or self.user.is_superuser

    def guardar_firma(self, data):
        self.firma_x = data
        self.firma_actualizada = timezone.now()
        self.save(update_fields=["firma_x", "firma_actualizada"])


# ============================================================ Nómina
class ExtractoNomina(models.Model):
    """Colilla de pago. Las deducciones de ley se calculan automáticamente en save()."""

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="extractos")
    periodo = models.DateField(help_text="Primer día del mes liquidado")
    devengado_base = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    bonificaciones = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    otras_deducciones = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    total_devengado = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    deduccion_salud = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    deduccion_pension = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    total_deducciones = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    neto_pagar = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-periodo", "empleado__user__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["empleado", "periodo"], name="un_extracto_por_periodo")
        ]

    def __str__(self):
        return f"{self.empleado} - {self.periodo:%Y-%m}"

    def calcular(self):
        """Salud 4% y Pensión 4% sobre el devengado base (salario), neto = devengado - deducciones."""
        if self.devengado_base is None:
            self.devengado_base = self.empleado.salario_base
        base = Decimal(self.devengado_base)
        self.total_devengado = _redondear(base + Decimal(self.bonificaciones or 0))
        self.deduccion_salud = _redondear(base * Decimal(settings.PORCENTAJE_SALUD))
        self.deduccion_pension = _redondear(base * Decimal(settings.PORCENTAJE_PENSION))
        self.total_deducciones = _redondear(
            self.deduccion_salud + self.deduccion_pension + Decimal(self.otras_deducciones or 0)
        )
        self.neto_pagar = _redondear(self.total_devengado - self.total_deducciones)

    def save(self, *args, **kwargs):
        self.periodo = self.periodo.replace(day=1)
        self.calcular()
        super().save(*args, **kwargs)


# ============================================================ Solicitudes con aprobación
class SolicitudBase(models.Model):
    """Campos comunes de un flujo solicitud -> aprobación/rechazo por el área responsable."""

    PENDIENTE, APROBADA, RECHAZADA = "PENDIENTE", "APROBADA", "RECHAZADA"
    ESTADOS = [(PENDIENTE, "Pendiente"), (APROBADA, "Aprobada"), (RECHAZADA, "Rechazada")]

    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDIENTE)
    revisado_por = models.ForeignKey(
        Empleado, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    comentario_revision = models.CharField("Comentario de revisión", max_length=300, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-creado"]

    def resolver(self, aprobar, revisor, comentario=""):
        self.estado = self.APROBADA if aprobar else self.RECHAZADA
        self.revisado_por = revisor
        self.comentario_revision = comentario[:300]
        self.fecha_resolucion = timezone.now()
        self.save()


class SolicitudVacaciones(SolicitudBase):
    TIPOS = [("VACACIONES", "Vacaciones"), ("PERMISO", "Permiso"), ("LICENCIA", "Licencia")]
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="vacaciones")
    tipo = models.CharField(max_length=12, choices=TIPOS, default="VACACIONES")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    motivo = models.CharField(max_length=300, blank=True)

    class Meta(SolicitudBase.Meta):
        verbose_name = "solicitud de vacaciones/permiso"

    @property
    def dias(self):
        return (self.fecha_fin - self.fecha_inicio).days + 1

    @property
    def detalle(self):
        return f"{self.fecha_inicio:%d/%m/%Y} → {self.fecha_fin:%d/%m/%Y} ({self.dias} días)"

    @property
    def tipo_texto(self):
        return self.get_tipo_display()

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La fecha fin no puede ser anterior a la fecha de inicio.")

    def __str__(self):
        return f"{self.empleado} · {self.tipo_texto} {self.detalle}"


class SolicitudAnticipo(SolicitudBase):
    TIPOS = [("ANTICIPO", "Anticipo de nómina"), ("PRESTAMO", "Préstamo")]
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="anticipos")
    tipo = models.CharField(max_length=10, choices=TIPOS, default="ANTICIPO")
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    cuotas = models.PositiveSmallIntegerField(default=1, help_text="Número de cuotas de descuento (1 a 24).")
    justificacion = models.CharField("Justificación", max_length=300)

    class Meta(SolicitudBase.Meta):
        verbose_name = "solicitud de anticipo/préstamo"

    @property
    def detalle(self):
        from core.templatetags.formatos import moneda

        return f"{moneda(self.monto)} en {self.cuotas} cuota(s)"

    @property
    def tipo_texto(self):
        return self.get_tipo_display()

    def __str__(self):
        return f"{self.empleado} · {self.tipo_texto} {self.monto}"


# ============================================================ Capacitación y comunicación
class CursoCapacitacion(models.Model):
    titulo = models.CharField(max_length=160)
    descripcion = models.TextField("Descripción", blank=True)
    contenido = models.TextField("Material formativo (texto)", blank=True)
    material_url = models.URLField("Enlace al material", blank=True)
    duracion_horas = models.PositiveSmallIntegerField("Duración (horas)", default=1)
    obligatorio = models.BooleanField(default=False, help_text="Se asigna automáticamente a nuevos colaboradores.")
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "curso de capacitación"

    def __str__(self):
        return self.titulo


class AsignacionCurso(models.Model):
    PENDIENTE, EN_CURSO, COMPLETADO = "PENDIENTE", "EN_CURSO", "COMPLETADO"
    ESTADOS = [(PENDIENTE, "Pendiente"), (EN_CURSO, "En curso"), (COMPLETADO, "Completado")]

    curso = models.ForeignKey(CursoCapacitacion, on_delete=models.CASCADE, related_name="asignaciones")
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="cursos")
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDIENTE)
    asignado = models.DateTimeField(auto_now_add=True)
    completado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["estado", "-asignado"]
        constraints = [models.UniqueConstraint(fields=["curso", "empleado"], name="un_curso_por_empleado")]

    def __str__(self):
        return f"{self.empleado} · {self.curso}"


class NoticiaCorporativa(models.Model):
    CATEGORIAS = [("COMUNICADO", "Comunicado oficial"), ("AVISO", "Aviso institucional"), ("NOVEDAD", "Novedad")]
    titulo = models.CharField(max_length=160)
    contenido = models.TextField()
    categoria = models.CharField(max_length=12, choices=CATEGORIAS, default="COMUNICADO")
    destacada = models.BooleanField(default=False)
    publicada = models.BooleanField(default=True)
    autor = models.ForeignKey(Empleado, null=True, on_delete=models.SET_NULL, related_name="noticias")
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-destacada", "-creada"]
        verbose_name = "noticia corporativa"

    def __str__(self):
        return self.titulo


# ============================================================ Tecnología
class TicketSoporte(models.Model):
    CATEGORIAS = [("HARDWARE", "Falla de hardware"), ("SOFTWARE", "Falla de software"), ("ACCESOS", "Accesos y cuentas")]
    PRIORIDADES = [("BAJA", "Baja"), ("MEDIA", "Media"), ("ALTA", "Alta"), ("CRITICA", "Crítica")]
    ESTADOS = [("ABIERTO", "Abierto"), ("EN_PROCESO", "En proceso"), ("RESUELTO", "Resuelto"), ("CERRADO", "Cerrado")]

    solicitante = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="tickets")
    categoria = models.CharField(max_length=10, choices=CATEGORIAS)
    prioridad = models.CharField(max_length=8, choices=PRIORIDADES, default="MEDIA")
    asunto = models.CharField(max_length=160)
    descripcion = models.TextField("Descripción del problema")
    estado = models.CharField(max_length=10, choices=ESTADOS, default="ABIERTO")
    asignado_a = models.ForeignKey(Empleado, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets_asignados")
    solucion = models.TextField("Respuesta / solución", blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "ticket de soporte"

    def __str__(self):
        return f"#{self.pk} {self.asunto}"

    @property
    def abierto(self):
        return self.estado in ("ABIERTO", "EN_PROCESO")


class ActivoTecnologico(models.Model):
    TIPOS = [("PORTATIL", "Portátil"), ("ESCRITORIO", "Equipo de escritorio"), ("MONITOR", "Monitor"),
             ("CELULAR", "Celular"), ("PERIFERICO", "Periférico"), ("OTRO", "Otro")]
    ESTADOS = [("ASIGNADO", "Asignado"), ("DISPONIBLE", "Disponible"),
               ("MANTENIMIENTO", "En mantenimiento"), ("BAJA", "Dado de baja")]

    tipo = models.CharField(max_length=12, choices=TIPOS)
    marca_modelo = models.CharField("Marca / modelo", max_length=120)
    serial = models.CharField(max_length=80, unique=True)
    asignado_a = models.ForeignKey(Empleado, null=True, blank=True, on_delete=models.SET_NULL, related_name="activos")
    estado = models.CharField(max_length=14, choices=ESTADOS, default="DISPONIBLE")
    fecha_entrega = models.DateField(null=True, blank=True)
    observaciones = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["tipo", "marca_modelo"]
        verbose_name = "activo tecnológico"

    def __str__(self):
        return f"{self.get_tipo_display()} {self.marca_modelo} ({self.serial})"


# ============================================================ Operaciones
class Espacio(models.Model):
    TIPOS = [("SALA", "Sala de juntas"), ("AUDIOVISUAL", "Recurso audiovisual"), ("ESPACIO", "Espacio físico")]
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=12, choices=TIPOS, default="SALA")
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name="espacios")
    capacidad = models.PositiveSmallIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["sede__nombre", "nombre"]

    def __str__(self):
        return f"{self.nombre} · {self.sede.ciudad}"


class ReservaEspacio(models.Model):
    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name="reservas")
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="reservas")
    titulo = models.CharField("Motivo / reunión", max_length=160)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    cancelada = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "hora_inicio"]

    def __str__(self):
        return f"{self.espacio} {self.fecha} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"

    def clean(self):
        if self.hora_inicio and self.hora_fin:
            if self.hora_fin <= self.hora_inicio:
                raise ValidationError("La hora de fin debe ser posterior a la hora de inicio.")
            if self.espacio_id and self.fecha:
                choque = ReservaEspacio.objects.filter(
                    espacio_id=self.espacio_id, fecha=self.fecha, cancelada=False,
                    hora_inicio__lt=self.hora_fin, hora_fin__gt=self.hora_inicio,
                ).exclude(pk=self.pk)
                if choque.exists():
                    raise ValidationError("El espacio ya está reservado en ese horario.")
