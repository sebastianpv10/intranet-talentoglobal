from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

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

INPUT_CLASS = (
    "w-full rounded-xl bg-slate-900/70 border border-slate-700 text-slate-100 "
    "placeholder-slate-500 px-4 py-2.5 focus:outline-none focus:ring-2 "
    "focus:ring-indigo-500 focus:border-indigo-500 text-sm transition"
)


class EstiloMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "h-5 w-5 rounded accent-indigo-500 bg-slate-900 border-slate-700 cursor-pointer"
            else:
                w.attrs["class"] = INPUT_CLASS
            if isinstance(w, forms.Textarea):
                w.attrs["rows"] = 3


# ---------------------------------------------------- Gestión Humana
class SedeForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Sede
        fields = ["nombre", "ciudad", "direccion", "telefono", "activa"]


class DepartamentoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Departamento
        fields = ["nombre", "descripcion"]


class EmpleadoForm(EstiloMixin, forms.ModelForm):
    first_name = forms.CharField(label="Nombres", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    email = forms.EmailField(label="Correo electrónico")

    class Meta:
        model = Empleado
        fields = [
            "first_name",
            "last_name",
            "documento",
            "email",
            "telefono",
            "direccion",
            "cargo",
            "salario_base",
            "fecha_ingreso",
            "tipo_contrato",
            "sede",
            "departamento",
            "rol",
            "activo",
        ]
        widgets = {
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sede"].queryset = Sede.objects.filter(activa=True) | Sede.objects.filter(
            pk=getattr(self.instance, "sede_id", None)
        )
        if self.instance.pk:
            u = self.instance.user
            self.fields["first_name"].initial = u.first_name
            self.fields["last_name"].initial = u.last_name
            self.fields["email"].initial = u.email

    def clean_documento(self):
        doc = self.cleaned_data["documento"].strip()
        qs = User.objects.filter(username=doc)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("Ya existe un usuario con este documento de identidad.")
        return doc

    def clean_salario_base(self):
        s = self.cleaned_data["salario_base"]
        if s <= 0:
            raise forms.ValidationError("El salario debe ser mayor a 0.")
        return s

    @transaction.atomic
    def save(self, commit=True):
        emp = super().save(commit=False)
        cd = self.cleaned_data
        nuevo = not emp.pk
        if nuevo:
            user = User(username=cd["documento"])
            user.set_password(settings.PASSWORD_PREDETERMINADA)
        else:
            user = emp.user
        user.first_name = cd["first_name"]
        user.last_name = cd["last_name"]
        user.email = cd["email"]
        user.is_active = cd["activo"]
        user.save()

        emp.user = user
        emp.save()

        if nuevo:
            # Asignar automáticamente los cursos obligatorios
            for c in CursoCapacitacion.objects.filter(obligatorio=True, activo=True):
                AsignacionCurso.objects.get_or_create(curso=c, empleado=emp)

        return emp


class PerfilAutogestionForm(EstiloMixin, forms.ModelForm):
    """Permite al colaborador actualizar sus propios datos personales de forma autónoma."""
    first_name = forms.CharField(label="Nombres", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    email = forms.EmailField(label="Correo electrónico")

    class Meta:
        model = Empleado
        fields = ["first_name", "last_name", "email", "telefono", "direccion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            u = self.instance.user
            self.fields["first_name"].initial = u.first_name
            self.fields["last_name"].initial = u.last_name
            self.fields["email"].initial = u.email

    @transaction.atomic
    def save(self, commit=True):
        emp = super().save(commit=False)
        cd = self.cleaned_data
        emp.user.first_name = cd["first_name"]
        emp.user.last_name = cd["last_name"]
        emp.user.email = cd["email"]
        emp.user.save()
        emp.save()
        return emp


class ExtractoNominaForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = ExtractoNomina
        fields = ["empleado", "periodo", "devengado_base", "bonificaciones", "otras_deducciones"]
        widgets = {"periodo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        help_texts = {
            "devengado_base": "Opcional: déjelo vacío para usar el salario base contractual.",
            "periodo": "Seleccione el mes a liquidar.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["empleado"].queryset = Empleado.objects.filter(activo=True).select_related("user")
        self.fields["devengado_base"].required = False

    def clean(self):
        cd = super().clean()
        emp = cd.get("empleado")
        per = cd.get("periodo")
        if emp and per:
            qs = ExtractoNomina.objects.filter(empleado=emp, periodo=per.replace(day=1))
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Ya existe una colilla emitida para ese empleado y periodo.")
        return cd


class SolicitudVacacionesForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = SolicitudVacaciones
        fields = ["tipo", "fecha_inicio", "fecha_fin", "motivo"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


# ---------------------------------------------------- Finanzas
class SolicitudAnticipoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = SolicitudAnticipo
        fields = ["tipo", "monto", "cuotas", "justificacion"]
        help_texts = {
            "monto": "Monto en pesos colombianos.",
            "cuotas": "Número de cuotas mensuales de descuento (1 a 12).",
        }

    def clean_monto(self):
        m = self.cleaned_data["monto"]
        if m <= 0:
            raise forms.ValidationError("El monto solicitado debe ser mayor a 0.")
        return m

    def clean_cuotas(self):
        c = self.cleaned_data["cuotas"]
        if c < 1 or c > 24:
            raise forms.ValidationError("El número de cuotas debe estar entre 1 y 24.")
        return c


# ---------------------------------------------------- Tecnología
class TicketSoporteForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = TicketSoporte
        fields = ["categoria", "prioridad", "asunto", "descripcion"]


class TicketAtencionForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = TicketSoporte
        fields = ["estado", "asignado_a", "solucion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asignado_a"].queryset = Empleado.objects.filter(
            activo=True, rol__in=[Empleado.ROL_IT, Empleado.ROL_ADMIN]
        ).select_related("user")
        self.fields["asignado_a"].required = False


class ActivoTecnologicoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = ActivoTecnologico
        fields = ["tipo", "marca_modelo", "serial", "asignado_a", "estado", "fecha_entrega", "observaciones"]
        widgets = {
            "fecha_entrega": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asignado_a"].queryset = Empleado.objects.filter(activo=True).select_related("user")
        self.fields["asignado_a"].required = False


# ---------------------------------------------------- Operaciones
class EspacioForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Espacio
        fields = ["nombre", "tipo", "sede", "capacidad", "activo"]


class ReservaEspacioForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = ReservaEspacio
        fields = ["espacio", "titulo", "fecha", "hora_inicio", "hora_fin"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["espacio"].queryset = Espacio.objects.filter(activo=True).select_related("sede")


# ---------------------------------------------------- Comunicación y Cursos
class NoticiaCorporativaForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = NoticiaCorporativa
        fields = ["titulo", "categoria", "contenido", "destacada", "publicada"]


class CursoCapacitacionForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = CursoCapacitacion
        fields = ["titulo", "descripcion", "contenido", "material_url", "duracion_horas", "obligatorio", "activo"]
