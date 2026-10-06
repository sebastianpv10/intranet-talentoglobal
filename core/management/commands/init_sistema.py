from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
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


class Command(BaseCommand):
    help = "Inicializa TalentoGlobal SAS: creador/admin (Sebastian Pamplona Varela), líderes de área y datos maestros."

    @transaction.atomic
    def handle(self, *args, **options):
        pwd = settings.PASSWORD_PREDETERMINADA

        # ------------------------------------------------ Sedes
        sedes = {}
        for nombre, ciudad, direc, tel in [
            ("Sede Principal Bogotá", "Bogotá", "Av. El Dorado # 68C-61, Torre 3", "+57 601 555 0100"),
            ("Sucursal Medellín", "Medellín", "Cra 43A # 1-50, El Poblado", "+57 604 555 0200"),
            ("Oficina Cali", "Cali", "Av. 6N # 28-10, Santa Mónica", "+57 602 555 0300"),
        ]:
            s, _ = Sede.objects.get_or_create(
                nombre=nombre, defaults={"ciudad": ciudad, "direccion": direc, "telefono": tel, "activa": True}
            )
            sedes[ciudad] = s

        # ------------------------------------------------ Departamentos
        deptos = {}
        for nombre, desc in [
            ("Dirección General", "Liderazgo corporativo, estrategia y administración central."),
            ("Recursos Humanos", "Gestión humana, selección, nómina, clima y bienestar."),
            ("Tecnología (IT)", "Desarrollo de software, infraestructura, ciberseguridad y soporte técnico."),
            ("Finanzas y Contabilidad", "Presupuestos, tesorería, cartera y liquidación financiera."),
            ("Operaciones y Logística", "Gestión de sedes, salas, eventos corporativos y procesos operativos."),
        ]:
            d, _ = Departamento.objects.get_or_create(nombre=nombre, defaults={"descripcion": desc})
            deptos[nombre] = d

        # ------------------------------------------------ Perfiles de Líderes
        lideres_data = [
            # username, first_name, last_name, email, doc, cargo, salario, depto, sede, rol, fecha_ingreso
            (
                "admin", "Sebastian", "Pamplona Varela", "sebastian.pamplona@talentoglobal.co",
                "1000000001", "Fundador & Director Ejecutivo (CEO)", 14500000,
                deptos["Dirección General"], sedes["Bogotá"], Empleado.ROL_ADMIN, date(2018, 1, 15), True
            ),
            (
                "rh_admin", "María Camila", "Gómez", "maria.gomez@talentoglobal.co",
                "1000000002", "Líder de Recursos Humanos", 7500000,
                deptos["Recursos Humanos"], sedes["Bogotá"], Empleado.ROL_RH, date(2020, 3, 1), False
            ),
            (
                "it_admin", "Carlos Andrés", "Restrepo", "carlos.restrepo@talentoglobal.co",
                "1000000003", "Líder de Tecnología & Ciberseguridad", 8200000,
                deptos["Tecnología (IT)"], sedes["Medellín"], Empleado.ROL_IT, date(2019, 8, 10), False
            ),
            (
                "finanzas_admin", "Ana Sofía", "Valencia", "ana.valencia@talentoglobal.co",
                "1000000004", "Líder Financiera y Contable", 7800000,
                deptos["Finanzas y Contabilidad"], sedes["Bogotá"], Empleado.ROL_FINANZAS, date(2021, 2, 1), False
            ),
            (
                "operaciones_admin", "Juan David", "Hincapié", "juan.hincapie@talentoglobal.co",
                "1000000005", "Líder de Operaciones y Logística", 6800000,
                deptos["Operaciones y Logística"], sedes["Cali"], Empleado.ROL_OPERACIONES, date(2021, 6, 15), False
            ),
        ]

        empleados_lideres = {}
        for username, fname, lname, email, doc, cargo, sal, dep, sde, rol, fingreso, es_super in lideres_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"first_name": fname, "last_name": lname, "email": email}
            )
            user.first_name = fname
            user.last_name = lname
            user.email = email
            user.is_staff = True
            user.is_superuser = es_super
            user.set_password(pwd)
            user.save()

            emp, _ = Empleado.objects.get_or_create(
                user=user,
                defaults=dict(
                    documento=doc,
                    cargo=cargo,
                    salario_base=sal,
                    fecha_ingreso=fingreso,
                    sede=sde,
                    departamento=dep,
                    rol=rol,
                    tipo_contrato="INDEFINIDO",
                    telefono="+57 300 123 4567",
                    direccion="Calle Corporativa TalentoGlobal",
                )
            )
            emp.rol = rol
            emp.save()
            empleados_lideres[username] = emp

        # ------------------------------------------------ Colaboradores base de prueba
        colaboradores_demo = [
            ("1020304050", "Laura", "Montoya", "laura.montoya@talentoglobal.co", "Desarrolladora Full-Stack", 5500000, deptos["Tecnología (IT)"], sedes["Medellín"], date(2022, 4, 1)),
            ("1030405060", "Felipe", "Cárdenas", "felipe.cardenas@talentoglobal.co", "Analista de Selección y Nómina", 3900000, deptos["Recursos Humanos"], sedes["Bogotá"], date(2023, 1, 10)),
            ("1040506070", "Daniela", "Suárez", "daniela.suarez@talentoglobal.co", "Analista de Tesorería", 4200000, deptos["Finanzas y Contabilidad"], sedes["Bogotá"], date(2023, 5, 20)),
        ]

        todos_empleados = list(empleados_lideres.values())
        for doc, fname, lname, email, cargo, sal, dep, sde, fingreso in colaboradores_demo:
            u, nuevo = User.objects.get_or_create(
                username=doc,
                defaults={"first_name": fname, "last_name": lname, "email": email}
            )
            if nuevo:
                u.set_password(pwd)
                u.save()
            emp, _ = Empleado.objects.get_or_create(
                user=u,
                defaults=dict(
                    documento=doc, cargo=cargo, salario_base=sal, fecha_ingreso=fingreso,
                    sede=sde, departamento=dep, rol=Empleado.ROL_EMPLEADO, tipo_contrato="INDEFINIDO",
                    telefono="+57 310 987 6543"
                )
            )
            todos_empleados.append(emp)

        # ------------------------------------------------ Cursos de Capacitación
        c1, _ = CursoCapacitacion.objects.get_or_create(
            titulo="Inducción Corporativa y Cultura TalentoGlobal",
            defaults={
                "descripcion": "Principios, valores y metodologías de trabajo en TalentoGlobal SAS.",
                "contenido": (
                    "¡Bienvenido a TalentoGlobal SAS! Nuestro propósito es conectar el talento del futuro con "
                    "las mayores oportunidades. En este curso aprenderás sobre nuestros pilares de innovación, "
                    "seguridad y crecimiento personal."
                ),
                "duracion_horas": 4,
                "obligatorio": True,
                "activo": True,
            }
        )
        c2, _ = CursoCapacitacion.objects.get_or_create(
            titulo="Ciberseguridad y Manejo Seguro de la Información",
            defaults={
                "descripcion": "Buenas prácticas de seguridad informática, contraseñas y prevención de phishing.",
                "contenido": (
                    "Aprende a identificar correos sospechosos, mantener tus dispositivos actualizados y proteger "
                    "la información confidencial de clientes y colaboradores."
                ),
                "duracion_horas": 2,
                "obligatorio": True,
                "activo": True,
            }
        )
        c3, _ = CursoCapacitacion.objects.get_or_create(
            titulo="Gestión del Tiempo y Productividad Ágil",
            defaults={
                "descripcion": "Herramientas de priorización, enfoque y trabajo colaborativo.",
                "contenido": "Técnicas Pomodoro, matriz de Eisenhower y sincronización de equipos asíncronos.",
                "duracion_horas": 3,
                "obligatorio": False,
                "activo": True,
            }
        )

        # Asignar cursos obligatorios
        for emp in todos_empleados:
            AsignacionCurso.objects.get_or_create(curso=c1, empleado=emp, defaults={"estado": AsignacionCurso.COMPLETADO})
            AsignacionCurso.objects.get_or_create(curso=c2, empleado=emp, defaults={"estado": AsignacionCurso.EN_CURSO})
            AsignacionCurso.objects.get_or_create(curso=c3, empleado=emp, defaults={"estado": AsignacionCurso.PENDIENTE})

        # ------------------------------------------------ Noticias Corporativas
        admin_emp = empleados_lideres["admin"]
        rh_emp = empleados_lideres["rh_admin"]
        it_emp = empleados_lideres["it_admin"]

        NoticiaCorporativa.objects.get_or_create(
            titulo="¡Lanzamiento oficial de la nueva Intranet Corporativa TalentoGlobal!",
            defaults={
                "contenido": (
                    "Hoy marcamos un nuevo hito en TalentoGlobal SAS con el despliegue de nuestra plataforma "
                    "100% autónoma y autogestionable. Ahora cada colaborador puede gestionar sus vacaciones, "
                    "firma digital X, certificados laborales y tickets de soporte en tiempo real."
                ),
                "categoria": "COMUNICADO",
                "destacada": True,
                "publicada": True,
                "autor": admin_emp,
            }
        )
        NoticiaCorporativa.objects.get_or_create(
            titulo="Jornada de Bienestar y Capacitaciones Virtuales",
            defaults={
                "contenido": (
                    "Recuerden revisar el módulo de cursos de capacitación asignados en su panel principal. "
                    "La formación continua es el motor que nos impulsa a conectar el talento del futuro."
                ),
                "categoria": "AVISO",
                "destacada": False,
                "publicada": True,
                "autor": rh_emp,
            }
        )
        NoticiaCorporativa.objects.get_or_create(
            titulo="Actualización de protocolos de Ciberseguridad",
            defaults={
                "contenido": (
                    "El equipo de IT habilitó el nuevo sistema de mesa de ayuda (Tickets) e inventario de activos. "
                    "Cualquier requerimiento técnico puede registrarse directamente desde su menú de Tecnología."
                ),
                "categoria": "NOVEDAD",
                "destacada": False,
                "publicada": True,
                "autor": it_emp,
            }
        )

        # ------------------------------------------------ Espacios Físicos / Salas
        s_bog = sedes["Bogotá"]
        s_med = sedes["Medellín"]
        e1, _ = Espacio.objects.get_or_create(
            nombre="Sala de Juntas Innovación (Bogotá)",
            defaults={"tipo": "SALA", "sede": s_bog, "capacidad": 14, "activo": True}
        )
        e2, _ = Espacio.objects.get_or_create(
            nombre="Kit Audiovisual Podcast & Streaming",
            defaults={"tipo": "AUDIOVISUAL", "sede": s_bog, "capacidad": 4, "activo": True}
        )
        e3, _ = Espacio.objects.get_or_create(
            nombre="Sala Creativa Antioquia (Medellín)",
            defaults={"tipo": "SALA", "sede": s_med, "capacidad": 10, "activo": True}
        )

        # Reserva de prueba
        ReservaEspacio.objects.get_or_create(
            espacio=e1,
            fecha=date.today() + timedelta(days=2),
            hora_inicio=time(10, 0),
            defaults={
                "empleado": admin_emp,
                "titulo": "Comité Directivo Mensual",
                "hora_fin": time(12, 0),
            }
        )

        # ------------------------------------------------ Activos Tecnológicos
        ActivoTecnologico.objects.get_or_create(
            serial="TG-MAC-2024-001",
            defaults={
                "tipo": "PORTATIL",
                "marca_modelo": "MacBook Pro M3 16GB",
                "asignado_a": admin_emp,
                "estado": "ASIGNADO",
                "fecha_entrega": date(2024, 1, 10),
                "observaciones": "Equipo asignado a Gerencia General."
            }
        )
        ActivoTecnologico.objects.get_or_create(
            serial="TG-LEN-2024-042",
            defaults={
                "tipo": "PORTATIL",
                "marca_modelo": "ThinkPad T14 Gen 4 Ryzen 7",
                "asignado_a": it_emp,
                "estado": "ASIGNADO",
                "fecha_entrega": date(2024, 2, 1),
                "observaciones": "Equipo de desarrollo e infraestructura."
            }
        )
        ActivoTecnologico.objects.get_or_create(
            serial="TG-MON-4K-015",
            defaults={
                "tipo": "MONITOR",
                "marca_modelo": "Dell UltraSharp 27 4K",
                "asignado_a": rh_emp,
                "estado": "ASIGNADO",
                "fecha_entrega": date(2024, 3, 1),
                "observaciones": "Monitor auxiliar sede Bogotá."
            }
        )

        # ------------------------------------------------ Tickets de Soporte
        TicketSoporte.objects.get_or_create(
            solicitante=rh_emp,
            asunto="Configuración de certificado SSL en nuevo dominio",
            defaults={
                "categoria": "SOFTWARE",
                "prioridad": "MEDIA",
                "descripcion": "Solicitud para validar los certificados SSL de los servicios corporativos.",
                "estado": "EN_PROCESO",
                "asignado_a": it_emp,
                "solucion": "En trámite de renovación con la entidad certificadora."
            }
        )

        # ------------------------------------------------ Nómina del mes actual
        mes_actual = date.today().replace(day=1)
        for emp in todos_empleados:
            ExtractoNomina.objects.get_or_create(
                empleado=emp,
                periodo=mes_actual,
                defaults={"devengado_base": emp.salario_base, "bonificaciones": 0, "otras_deducciones": 0}
            )

        # ------------------------------------------------ Solicitudes de ejemplo
        SolicitudVacaciones.objects.get_or_create(
            empleado=rh_emp,
            fecha_inicio=date.today() + timedelta(days=20),
            fecha_fin=date.today() + timedelta(days=27),
            defaults={
                "tipo": "VACACIONES",
                "motivo": "Periodo de descanso legal.",
                "estado": SolicitudVacaciones.APROBADA,
                "revisado_por": admin_emp,
                "comentario_revision": "Aprobado por Dirección General.",
            }
        )

        SolicitudAnticipo.objects.get_or_create(
            empleado=todos_empleados[-1],
            monto=800000,
            defaults={
                "tipo": "ANTICIPO",
                "cuotas": 2,
                "justificacion": "Gastos médicos personales imprevistos.",
                "estado": SolicitudAnticipo.PENDIENTE,
            }
        )

        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(self.style.SUCCESS("  SISTEMA TALENTOGLOBAL SAS INICIALIZADO CON ÉXITO"))
        self.stdout.write(self.style.SUCCESS("  Eslogan: 'Conectando el talento del futuro'"))
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(self.style.WARNING("CUENTAS Y CREDENCIALES CONFIGURADAS (Contraseña: admin):"))
        self.stdout.write("  - Superadministrador: admin             | Sebastian Pamplona Varela")
        self.stdout.write("  - Talento Humano:     rh_admin          | María Camila Gómez")
        self.stdout.write("  - Tecnología (IT):    it_admin          | Carlos Andrés Restrepo")
        self.stdout.write("  - Finanzas:           finanzas_admin    | Ana Sofía Valencia")
        self.stdout.write("  - Operaciones:        operaciones_admin | Juan David Hincapié")
        self.stdout.write(self.style.SUCCESS("=" * 65))
