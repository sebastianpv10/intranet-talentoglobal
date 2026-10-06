from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

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


class TalentoGlobalMultiAreaTests(TestCase):
    def setUp(self):
        # Sedes y Deptos
        self.sede = Sede.objects.create(nombre="Sede Bogotá", ciudad="Bogotá")
        self.depto_rh = Departamento.objects.create(nombre="Recursos Humanos")
        self.depto_it = Departamento.objects.create(nombre="Tecnología (IT)")
        self.depto_fin = Departamento.objects.create(nombre="Finanzas")

        # Superadmin: Sebastian Pamplona Varela
        self.u_admin = User.objects.create_superuser("admin", "admin@tg.co", "admin")
        self.u_admin.first_name = "Sebastian"
        self.u_admin.last_name = "Pamplona Varela"
        self.u_admin.save()
        self.emp_admin = Empleado.objects.create(
            user=self.u_admin, documento="1000000001", cargo="CEO", salario_base=Decimal("15000000"),
            fecha_ingreso=date(2018, 1, 1), sede=self.sede, departamento=self.depto_rh, rol=Empleado.ROL_ADMIN
        )

        # Líder RH
        self.u_rh = User.objects.create_user("rh_admin", "rh@tg.co", "admin")
        self.emp_rh = Empleado.objects.create(
            user=self.u_rh, documento="1000000002", cargo="Líder RH", salario_base=Decimal("7500000"),
            fecha_ingreso=date(2020, 1, 1), sede=self.sede, departamento=self.depto_rh, rol=Empleado.ROL_RH
        )

        # Empleado estándar
        self.u_emp = User.objects.create_user("1020304050", "colab@tg.co", "admin")
        self.u_emp.first_name = "Laura"
        self.u_emp.last_name = "Montoya"
        self.u_emp.save()
        self.emp_colab = Empleado.objects.create(
            user=self.u_emp, documento="1020304050", cargo="Desarrolladora", salario_base=Decimal("5000000"),
            fecha_ingreso=date(2022, 1, 1), sede=self.sede, departamento=self.depto_it, rol=Empleado.ROL_EMPLEADO
        )

    def test_01_nomina_deducciones_automaticas(self):
        """Verifica que salud (4%) y pensión (4%) se calculen automáticamente sobre el devengado base."""
        ext = ExtractoNomina.objects.create(
            empleado=self.emp_colab,
            periodo=date(2026, 10, 1),
            devengado_base=Decimal("5000000"),
            bonificaciones=Decimal("200000"),
            otras_deducciones=Decimal("50000"),
        )
        self.assertEqual(ext.total_devengado, Decimal("5200000"))
        self.assertEqual(ext.deduccion_salud, Decimal("200000"))   # 4% de 5M
        self.assertEqual(ext.deduccion_pension, Decimal("200000")) # 4% de 5M
        self.assertEqual(ext.total_deducciones, Decimal("450000")) # 200k + 200k + 50k
        self.assertEqual(ext.neto_pagar, Decimal("4750000"))       # 5.2M - 450k

    def test_02_login_y_dashboard(self):
        c = Client()
        logueado = c.login(username="admin", password="admin")
        self.assertTrue(logueado)
        resp = c.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sebastian")
        self.assertContains(resp, "TalentoGlobal")

    def test_03_firma_x_actualizacion(self):
        c = Client()
        c.login(username="1020304050", password="admin")
        fake_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        resp = c.post(reverse("firma_x"), {"firma": fake_png})
        self.assertEqual(resp.status_code, 302)
        self.emp_colab.refresh_from_db()
        self.assertTrue(self.emp_colab.firma_x.startswith("data:image/png;base64,"))

    def test_04_certificado_laboral(self):
        c = Client()
        c.login(username="1020304050", password="admin")
        resp = c.get(reverse("certificado"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "CERTIFICA QUE")
        self.assertContains(resp, "Laura Montoya")
        self.assertContains(resp, "5.000.000")

    def test_05_creacion_empleado_con_password_default(self):
        c = Client()
        c.login(username="rh_admin", password="admin")
        resp = c.post(reverse("empleado_create"), {
            "first_name": "Pedro",
            "last_name": "Pérez",
            "documento": "999888777",
            "email": "pedro@tg.co",
            "telefono": "3001112233",
            "direccion": "Calle 10",
            "cargo": "Consultor",
            "salario_base": "4000000",
            "fecha_ingreso": "2024-05-01",
            "tipo_contrato": "INDEFINIDO",
            "sede": self.sede.pk,
            "departamento": self.depto_it.pk,
            "rol": Empleado.ROL_EMPLEADO,
            "activo": "on",
        })
        self.assertEqual(resp.status_code, 302)
        # El nuevo usuario puede loguearse con contraseña 'admin'
        c_nuevo = Client()
        self.assertTrue(c_nuevo.login(username="999888777", password="admin"))

    def test_06_flujo_vacaciones_y_aprobacion(self):
        c = Client()
        c.login(username="1020304050", password="admin")
        resp = c.post(reverse("vacaciones_solicitar"), {
            "tipo": "VACACIONES",
            "fecha_inicio": date.today() + timedelta(days=10),
            "fecha_fin": date.today() + timedelta(days=15),
            "motivo": "Descanso anual",
        })
        self.assertEqual(resp.status_code, 302)
        sol = SolicitudVacaciones.objects.get(empleado=self.emp_colab)
        self.assertEqual(sol.estado, SolicitudVacaciones.PENDIENTE)

        # RH la aprueba
        c_rh = Client()
        c_rh.login(username="rh_admin", password="admin")
        resp_aprob = c_rh.post(reverse("vacaciones_resolver", args=[sol.pk, "aprobar"]), {"comentario": "Aprobado"})
        self.assertEqual(resp_aprob.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, SolicitudVacaciones.APROBADA)

    def test_07_reserva_espacios_evita_colisiones(self):
        espacio = Espacio.objects.create(nombre="Sala VIP", sede=self.sede, capacidad=8)
        # Reserva 1: 10:00 a 12:00
        ReservaEspacio.objects.create(
            espacio=espacio, empleado=self.emp_admin, titulo="Reunión 1",
            fecha=date.today(), hora_inicio=time(10, 0), hora_fin=time(12, 0)
        )

        # Intento de colisión: 11:00 a 13:00
        res_colision = ReservaEspacio(
            espacio=espacio, empleado=self.emp_colab, titulo="Reunión Choque",
            fecha=date.today(), hora_inicio=time(11, 0), hora_fin=time(13, 0)
        )
        with self.assertRaises(Exception):
            res_colision.full_clean()

    def test_08_exportacion_excel(self):
        c = Client()
        c.login(username="admin", password="admin")
        resp = c.get(reverse("exportar_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
