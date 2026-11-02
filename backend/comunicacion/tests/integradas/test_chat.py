from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from comunicacion.models import Mensaje
from comunicacion.servicios import enviar_mensaje
from notificaciones.models import Notificacion

from comunicacion.tests import factories as f


class EnviarMensajeTests(TestCase):
    def setUp(self):
        self.ana, self.profe = f.estudiante().usuario, f.docente().usuario

    def test_guarda_el_mensaje_y_avisa_al_receptor(self):
        enviar_mensaje(self.ana, self.profe.pk, "  Hola profe  ")
        self.assertEqual(Mensaje.objects.get().contenido, "Hola profe")
        n = Notificacion.objects.get(usuario=self.profe)
        self.assertEqual(n.tipo, "MENSAJE")
        self.assertIn(self.ana.nombres, n.mensaje)

    def test_varios_mensajes_seguidos_generan_una_sola_notificacion(self):
        for texto in ("uno", "dos", "tres"):
            enviar_mensaje(self.ana, self.profe.pk, texto)
        self.assertEqual(Notificacion.objects.filter(usuario=self.profe).count(), 1)

    def test_si_ya_la_leyo_la_siguiente_mensaje_vuelve_a_avisar(self):
        enviar_mensaje(self.ana, self.profe.pk, "uno")
        Notificacion.objects.filter(usuario=self.profe).update(leida=True)
        enviar_mensaje(self.ana, self.profe.pk, "dos")
        self.assertEqual(Notificacion.objects.filter(usuario=self.profe, leida=False).count(), 1)

    def test_no_guarda_ni_avisa_si_no_corresponde(self):
        with self.assertRaises(ValidationError):
            enviar_mensaje(self.ana, f.administrador().pk, "hola")
        with self.assertRaises(ValidationError):
            enviar_mensaje(self.ana, self.ana.pk, "yo conmigo")
        self.assertEqual(Mensaje.objects.count(), 0)
        self.assertEqual(Notificacion.objects.count(), 0)


class BandejaDocenteTests(TestCase):
    def setUp(self):
        self.docente = f.docente()
        self.paralelo = f.paralelo(self.docente)
        self.ana, self.beto = f.estudiante(), f.estudiante()
        f.inscribir(self.ana, self.paralelo)
        self.url = reverse("docente_mensajes", args=[self.paralelo.curso_id])
        f.iniciar_sesion(self.client, self.docente)

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        self.client.cookies.clear()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_un_estudiante_no_entra_a_la_ruta_del_docente(self):
        f.iniciar_sesion(self.client, self.ana)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_muestra_la_bandeja(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_la_lista_ordena_por_ultimo_mensaje_y_cuenta_los_no_leidos(self):
        enviar_mensaje(self.ana.usuario, self.docente.pk, "primero")
        enviar_mensaje(self.beto.usuario, self.docente.pk, "segundo")
        enviar_mensaje(self.beto.usuario, self.docente.pk, "tercero")
        convs = self.client.get(self.url).context["conversaciones"]
        self.assertEqual([c["usuario"].pk for c in convs], [self.beto.pk, self.ana.pk])
        self.assertEqual([c["no_leidos"] for c in convs], [2, 1])
        self.assertEqual(convs[0]["ultimo"], "tercero")

    def test_abrir_una_conversacion_marca_sus_mensajes_como_leidos(self):
        enviar_mensaje(self.ana.usuario, self.docente.pk, "hola")
        self.assertEqual(Notificacion.objects.filter(usuario=self.docente.usuario, leida=False).count(), 1)
        r = self.client.get(self.url, {"con": self.ana.pk})
        self.assertEqual(r.context["abierta"]["usuario"].pk, self.ana.pk)
        self.assertFalse(Mensaje.objects.filter(receptor=self.docente.usuario, leido=False).exists())
        self.assertFalse(Notificacion.objects.filter(usuario=self.docente.usuario, leida=False).exists())

    def test_los_mensajes_propios_se_marcan_como_mios(self):
        enviar_mensaje(self.ana.usuario, self.docente.pk, "pregunta")
        enviar_mensaje(self.docente.usuario, self.ana.pk, "respuesta")
        items = self.client.get(self.url, {"con": self.ana.pk}).context["abierta"]["mensajes"]
        mensajes = [i for i in items if "texto" in i]
        self.assertEqual([(m["texto"], m["es_mio"]) for m in mensajes], [("pregunta", False), ("respuesta", True)])
        self.assertTrue(items[0]["separador"])

    def test_enviar_por_formulario_guarda_y_vuelve_a_la_conversacion(self):
        r = self.client.post(self.url, {"con": self.ana.pk, "texto": "Hola Ana"})
        self.assertRedirects(r, f"{self.url}?con={self.ana.pk}", fetch_redirect_response=False)
        self.assertEqual(Mensaje.objects.get().contenido, "Hola Ana")

    def test_enviar_a_quien_no_corresponde_muestra_error_y_no_guarda(self):
        admin = f.administrador()
        r = self.client.post(self.url, {"con": admin.pk, "texto": "hola"})
        self.assertEqual(Mensaje.objects.count(), 0)
        self.assertTrue(any(m.level_tag == "error" for m in get_messages(r.wsgi_request)))

    def test_no_se_puede_abrir_un_chat_con_uno_mismo(self):
        self.assertIsNone(self.client.get(self.url, {"con": self.docente.pk}).context["abierta"])

    def test_el_nuevo_chat_lista_a_todos_menos_a_uno_mismo_y_a_los_inactivos(self):
        otro_docente = f.docente()
        f.estudiante(estado=False)
        grupos = {g["titulo"]: [p["usuario"].pk for p in g["personas"]]
                  for g in self.client.get(self.url).context["grupos"]}
        self.assertEqual(grupos["Docentes"], [otro_docente.pk])
        self.assertCountEqual(grupos["Estudiantes"], [self.ana.pk, self.beto.pk])
        self.assertNotIn(self.docente.pk, grupos["Docentes"])


class BandejaEstudianteTests(TestCase):
    def setUp(self):
        self.docente = f.docente()
        self.ana, self.beto = f.estudiante(), f.estudiante()   # NO comparten paralelo
        f.inscribir(self.ana, f.paralelo(self.docente))
        self.url = reverse("estudiante_mensajes")
        f.iniciar_sesion(self.client, self.ana)

    def test_un_docente_no_entra_a_la_ruta_del_estudiante(self):
        f.iniciar_sesion(self.client, self.docente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_puede_escribirle_a_un_estudiante_de_otro_paralelo(self):
        self.client.post(self.url, {"con": self.beto.pk, "texto": "Hola Beto"})
        self.assertEqual(Mensaje.objects.get().receptor_id, self.beto.pk)

    def test_puede_escribirle_a_un_docente_que_no_es_el_suyo(self):
        otro = f.docente()
        self.client.post(self.url, {"con": otro.pk, "texto": "Hola profe"})
        self.assertEqual(Mensaje.objects.get().receptor_id, otro.pk)

    def test_la_respuesta_le_llega_con_aviso_y_conteo(self):
        enviar_mensaje(self.beto.usuario, self.ana.pk, "¿Hacemos la tarea?")
        convs = self.client.get(self.url).context["conversaciones"]
        self.assertEqual(convs[0]["no_leidos"], 1)
        self.assertEqual(convs[0]["rol"], "Estudiante")

    def test_el_nuevo_chat_muestra_docentes_y_companeros(self):
        titulos = [g["titulo"] for g in self.client.get(self.url).context["grupos"]]
        self.assertEqual(titulos, ["Docentes", "Estudiantes"])