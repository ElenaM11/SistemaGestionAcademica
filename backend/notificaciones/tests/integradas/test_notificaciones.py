from django.test import RequestFactory, TestCase
from django.urls import reverse

from comunicacion.tests import factories as f
from notificaciones.context_processors import no_leidas
from notificaciones.models import Notificacion
from notificaciones.services import notificar_paralelo, notificar_usuarios


class ServiciosTests(TestCase):
    def test_notificar_usuarios_no_repite_personas(self):
        a, b = f.estudiante(), f.estudiante()
        self.assertEqual(notificar_usuarios([a.pk, b.pk, a.pk], "AVISO", "Hola"), 2)
        self.assertEqual(Notificacion.objects.count(), 2)

    def test_notificar_paralelo_solo_llega_a_los_estudiantes_activos(self):
        p = f.paralelo(f.docente())
        activo, retirado = f.estudiante(), f.estudiante()
        f.inscribir(activo, p)
        f.inscribir(retirado, p, estado="INACTIVO")
        self.assertEqual(notificar_paralelo(p, "AVISO", "Hola"), 1)
        self.assertEqual(Notificacion.objects.get().usuario_id, activo.pk)

    def test_marcar_leida_es_idempotente(self):
        n = Notificacion.objects.create(usuario=f.estudiante().usuario, tipo="OTRO", mensaje="x")
        n.marcar_leida()
        n.marcar_leida()
        n.refresh_from_db()
        self.assertTrue(n.leida)


class VistasTests(TestCase):
    def setUp(self):
        self.ana = f.estudiante()
        self.otra = f.estudiante()
        self.n1 = Notificacion.objects.create(usuario=self.ana.usuario, tipo="AVISO", mensaje="Aviso 1")
        self.n2 = Notificacion.objects.create(usuario=self.ana.usuario, tipo="OTRO", mensaje="Otra cosa", leida=True)
        self.ajena = Notificacion.objects.create(usuario=self.otra.usuario, tipo="AVISO", mensaje="No es tuya")
        f.iniciar_sesion(self.client, self.ana)
        self.lista = reverse("notificaciones")

    def test_sin_sesion_redirige_al_login(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.get(self.lista).status_code, 302)

    def test_la_lista_solo_trae_las_propias(self):
        r = self.client.get(self.lista)
        self.assertEqual(r.status_code, 200)
        self.assertCountEqual([n.pk for n in r.context["pagina"]], [self.n1.pk, self.n2.pk])
        self.assertEqual(r.context["sin_leer"], 1)

    def test_el_filtro_sin_leer(self):
        r = self.client.get(self.lista, {"solo": "no_leidas"})
        self.assertEqual([n.pk for n in r.context["pagina"]], [self.n1.pk])

    def test_abrir_marca_como_leida_y_lleva_al_destino_del_tipo(self):
        r = self.client.get(reverse("notificaciones_abrir", args=[self.n1.pk]))
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.leida)
        self.assertRedirects(r, reverse("estudiante_avisos"), fetch_redirect_response=False)

    def test_abrir_un_tipo_sin_destino_vuelve_a_la_lista(self):
        Notificacion.objects.filter(pk=self.n2.pk).update(leida=False)
        r = self.client.get(reverse("notificaciones_abrir", args=[self.n2.pk]))
        self.assertRedirects(r, self.lista, fetch_redirect_response=False)

    def test_no_se_puede_abrir_la_notificacion_de_otra_persona(self):
        self.assertEqual(self.client.get(reverse("notificaciones_abrir", args=[self.ajena.pk])).status_code, 404)
        self.ajena.refresh_from_db()
        self.assertFalse(self.ajena.leida)

    def test_marcar_todas_solo_afecta_a_las_propias_y_solo_por_post(self):
        self.client.get(reverse("notificaciones_leer_todas"))
        self.n1.refresh_from_db()
        self.assertFalse(self.n1.leida)
        self.client.post(reverse("notificaciones_leer_todas"))
        self.n1.refresh_from_db()
        self.ajena.refresh_from_db()
        self.assertTrue(self.n1.leida)
        self.assertFalse(self.ajena.leida)


class InsigniaTests(TestCase):
    def pedir(self, usuario_id=None):
        r = RequestFactory().get("/")
        r.session = {"usuario_id": usuario_id} if usuario_id else {}
        return no_leidas(r)

    def test_sin_sesion_no_agrega_nada(self):
        self.assertEqual(self.pedir(), {})

    def test_cuenta_solo_las_no_leidas_de_esa_persona(self):
        u = f.estudiante().usuario
        Notificacion.objects.create(usuario=u, mensaje="a")
        Notificacion.objects.create(usuario=u, mensaje="b", leida=True)
        Notificacion.objects.create(usuario=f.estudiante().usuario, mensaje="c")
        self.assertEqual(self.pedir(u.pk)["notif_no_leidas"], 1)

    def test_mas_de_99_se_muestra_como_99_mas(self):
        u = f.estudiante().usuario
        Notificacion.objects.bulk_create([Notificacion(usuario=u, mensaje=str(i)) for i in range(120)])
        datos = self.pedir(u.pk)
        self.assertEqual((datos["notif_no_leidas"], datos["notif_no_leidas_texto"]), (120, "99+"))