from datetime import time
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from asistencia.models import SesionClase
from comunicacion.models import SesionParticipante
from notificaciones.models import Notificacion

from comunicacion.tests import factories as f

CONF = dict(LIVEKIT_URL="wss://prueba.livekit.cloud", LIVEKIT_API_KEY="APIprueba",
            LIVEKIT_API_SECRET="secreto-de-prueba-bastante-largo-1234567890")
EN_CURSO = SesionClase.Estado.EN_CURSO


class IniciarClaseTests(TestCase):
    def setUp(self):
        self.docente = f.docente()
        self.paralelo = f.paralelo(self.docente)
        self.ana = f.estudiante()
        f.inscribir(self.ana, self.paralelo)
        f.inscribir(f.estudiante(), self.paralelo, estado="INACTIVO")
        self.url = reverse("docente_clase_iniciar", args=[self.paralelo.curso_id])
        f.iniciar_sesion(self.client, self.docente)

    def iniciar(self, **datos):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {"id_paralelo": self.paralelo.pk, "tema": "Present simple", **datos})

    def test_iniciar_crea_la_sesion_en_curso_y_va_a_la_sala(self):
        r = self.iniciar()
        s = SesionClase.objects.get()
        self.assertRedirects(r, reverse("docente_clase_sala", args=[self.paralelo.curso_id, s.pk]), fetch_redirect_response=False)
        self.assertEqual((s.estado, s.tema), (EN_CURSO, "Present simple"))
        self.assertEqual(s.sala_livekit, f"clase-{s.pk}")
        self.assertIsNotNone(s.inicio_real)

    def test_avisa_solo_a_los_estudiantes_activos(self):
        self.iniciar()
        self.assertEqual(list(Notificacion.objects.values_list("usuario_id", "tipo")), [(self.ana.pk, "CLASE")])

    def test_reutiliza_la_sesion_programada_de_hoy(self):
        from django.utils import timezone
        previa = SesionClase.objects.create(paralelo=self.paralelo, fecha=timezone.localdate(), hora_inicio=time(8))
        self.iniciar()
        self.assertEqual(SesionClase.objects.count(), 1)
        previa.refresh_from_db()
        self.assertEqual(previa.estado, EN_CURSO)

    def test_iniciar_dos_veces_reanuda_la_misma_clase(self):
        self.iniciar()
        self.iniciar()
        self.assertEqual(SesionClase.objects.count(), 1)

    def test_el_tema_es_obligatorio(self):
        r = self.iniciar(tema="  ")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SesionClase.objects.count(), 0)
        self.assertIn("tema", r.context["error"].lower())

    def test_no_puede_iniciar_el_paralelo_de_otro_docente(self):
        ajeno = f.paralelo(f.docente())
        r = self.iniciar(id_paralelo=ajeno.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SesionClase.objects.count(), 0)

    def test_una_clase_en_curso_de_ayer_se_cierra_sola(self):
        vieja = SesionClase.objects.create(paralelo=self.paralelo, fecha="2020-01-01", estado=EN_CURSO)
        self.client.get(self.url)
        vieja.refresh_from_db()
        self.assertEqual(vieja.estado, SesionClase.Estado.FINALIZADA)


class SalaDocenteTests(TestCase):
    def setUp(self):
        self.docente = f.docente()
        self.paralelo = f.paralelo(self.docente)
        self.sesion = SesionClase.objects.create(paralelo=self.paralelo, fecha="2026-11-02", estado=EN_CURSO,
                                                 sala_livekit="clase-1", tema="Tema")
        self.curso_id = self.paralelo.curso_id
        f.iniciar_sesion(self.client, self.docente)

    def url(self, nombre):
        return reverse(nombre, args=[self.curso_id, self.sesion.pk])

    def test_la_sala_abre_y_registra_la_entrada_del_docente(self):
        self.assertEqual(self.client.get(self.url("docente_clase_sala")).status_code, 200)
        self.assertTrue(SesionParticipante.objects.filter(sesion=self.sesion, usuario=self.docente.usuario).exists())

    def test_otro_docente_recibe_404(self):
        f.iniciar_sesion(self.client, f.docente())
        self.assertEqual(self.client.get(self.url("docente_clase_sala")).status_code, 404)

    def test_una_clase_finalizada_manda_de_vuelta_a_iniciar(self):
        self.sesion.estado = SesionClase.Estado.FINALIZADA
        self.sesion.save()
        r = self.client.get(self.url("docente_clase_sala"))
        self.assertRedirects(r, reverse("docente_clase_iniciar", args=[self.curso_id]), fetch_redirect_response=False)

    @patch("comunicacion.views.livekit.cerrar_sala")
    def test_finalizar_cierra_todo_y_lleva_a_la_asistencia(self, cerrar):
        ana = f.estudiante().usuario
        SesionParticipante.registrar_ingreso(self.sesion, ana)
        r = self.client.post(self.url("docente_clase_finalizar"))
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionClase.Estado.FINALIZADA)
        self.assertIsNotNone(self.sesion.fin_real)
        self.assertFalse(SesionParticipante.objects.filter(sesion=self.sesion, hora_salida__isnull=True).exists())
        cerrar.assert_called_once_with("clase-1")
        self.assertIn(reverse("docente_asistencia", args=[self.curso_id]), r["Location"])
        self.assertIn("fecha=2026-11-02", r["Location"])

    @patch("comunicacion.views.livekit.cerrar_sala")
    def test_finalizar_solo_se_hace_por_post(self, cerrar):
        self.assertEqual(self.client.get(self.url("docente_clase_finalizar")).status_code, 405)
        cerrar.assert_not_called()

    @patch("comunicacion.views.livekit.cerrar_sala")
    def test_otro_docente_no_puede_finalizar_la_clase(self, cerrar):
        f.iniciar_sesion(self.client, f.docente())
        self.assertEqual(self.client.post(self.url("docente_clase_finalizar")).status_code, 404)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EN_CURSO)


@override_settings(**CONF)
class TokenViewTests(TestCase):
    def setUp(self):
        self.docente = f.docente()
        self.paralelo = f.paralelo(self.docente)
        self.ana = f.estudiante()
        f.inscribir(self.ana, self.paralelo)
        self.sesion = SesionClase.objects.create(paralelo=self.paralelo, fecha="2026-11-02", estado=EN_CURSO)
        self.url = reverse("comunicacion_token", args=[self.sesion.pk])

    def test_sin_sesion_es_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_el_docente_de_la_clase_recibe_token_y_url(self):
        f.iniciar_sesion(self.client, self.docente)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["url"], CONF["LIVEKIT_URL"])
        self.assertTrue(r.json()["token"])
        self.assertIn("no-store", r["Cache-Control"])

    def test_el_estudiante_inscrito_recibe_token(self):
        f.iniciar_sesion(self.client, self.ana)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_un_estudiante_no_inscrito_es_403(self):
        f.iniciar_sesion(self.client, f.estudiante())
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_un_estudiante_con_inscripcion_inactiva_es_403(self):
        retirado = f.estudiante()
        f.inscribir(retirado, self.paralelo, estado="INACTIVO")
        f.iniciar_sesion(self.client, retirado)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_otro_docente_es_403(self):
        f.iniciar_sesion(self.client, f.docente())
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_el_administrador_es_403(self):
        f.iniciar_sesion(self.client, f.administrador())
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_clase_que_no_esta_en_curso_es_409(self):
        self.sesion.estado = SesionClase.Estado.FINALIZADA
        self.sesion.save()
        f.iniciar_sesion(self.client, self.docente)
        self.assertEqual(self.client.get(self.url).status_code, 409)

    @override_settings(LIVEKIT_API_SECRET="")
    def test_sin_configurar_livekit_es_503(self):
        f.iniciar_sesion(self.client, self.docente)
        self.assertEqual(self.client.get(self.url).status_code, 503)

    def test_solo_se_permite_get(self):
        f.iniciar_sesion(self.client, self.docente)
        self.assertEqual(self.client.post(self.url).status_code, 405)


class ClasesEstudianteTests(TestCase):
    def setUp(self):
        self.docente = f.docente()
        self.paralelo = f.paralelo(self.docente)
        self.ana = f.estudiante()
        f.inscribir(self.ana, self.paralelo)
        from django.utils import timezone
        self.sesion = SesionClase.objects.create(paralelo=self.paralelo, fecha=timezone.localdate(), estado=EN_CURSO,
                                                 tema="Tema", sala_livekit="clase-1")
        f.iniciar_sesion(self.client, self.ana)

    def test_la_lista_muestra_la_clase_en_vivo(self):
        clases = self.client.get(reverse("estudiante_clases_vivo")).context["clases"]
        self.assertEqual([(c["pk"], c["estado_vista"]) for c in clases], [(self.sesion.pk, "en_vivo")])

    def test_no_muestra_clases_de_paralelos_donde_no_esta(self):
        f.iniciar_sesion(self.client, f.estudiante())
        self.assertEqual(self.client.get(reverse("estudiante_clases_vivo")).context["clases"], [])

    def test_entrar_a_la_sala_registra_la_participacion(self):
        r = self.client.get(reverse("estudiante_clase_sala", args=[self.sesion.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(SesionParticipante.objects.filter(sesion=self.sesion, usuario=self.ana.usuario).exists())

    def test_un_estudiante_no_inscrito_no_entra_a_la_sala(self):
        f.iniciar_sesion(self.client, f.estudiante())
        self.assertEqual(self.client.get(reverse("estudiante_clase_sala", args=[self.sesion.pk])).status_code, 404)

    def test_no_se_entra_a_una_clase_terminada(self):
        self.sesion.estado = SesionClase.Estado.FINALIZADA
        self.sesion.save()
        r = self.client.get(reverse("estudiante_clase_sala", args=[self.sesion.pk]))
        self.assertRedirects(r, reverse("estudiante_clases_vivo"), fetch_redirect_response=False)

    def test_salir_registra_la_hora_de_salida(self):
        self.client.get(reverse("estudiante_clase_sala", args=[self.sesion.pk]))
        self.client.post(reverse("estudiante_clase_salir", args=[self.sesion.pk]))
        self.assertIsNotNone(SesionParticipante.objects.get().hora_salida)