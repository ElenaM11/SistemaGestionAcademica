from django.core.exceptions import ValidationError
from django.test import TestCase

from comunicacion.models import Aviso, Mensaje, SesionParticipante
from asistencia.models import SesionClase

from comunicacion.tests import factories as f


class MensajeTests(TestCase):
    def test_enviar_guarda_un_mensaje_no_leido(self):
        a, b = f.estudiante().usuario, f.docente().usuario
        m = Mensaje(emisor=a, receptor=b, contenido="Hola profe").enviar()
        self.assertFalse(m.leido)
        self.assertEqual(Mensaje.objects.count(), 1)

    def test_no_se_puede_escribir_a_un_administrador(self):
        with self.assertRaises(ValidationError):
            Mensaje(emisor=f.estudiante().usuario, receptor=f.administrador(), contenido="hola").enviar()

    def test_marcar_leido(self):
        m = Mensaje(emisor=f.estudiante().usuario, receptor=f.docente().usuario, contenido="hola").enviar()
        m.marcar_leido()
        m.refresh_from_db()
        self.assertTrue(m.leido)

    def test_conversacion_incluye_ambos_sentidos_y_nada_mas(self):
        a, b, c = f.estudiante().usuario, f.docente().usuario, f.estudiante().usuario
        Mensaje(emisor=a, receptor=b, contenido="1").enviar()
        Mensaje(emisor=b, receptor=a, contenido="2").enviar()
        Mensaje(emisor=a, receptor=c, contenido="3").enviar()
        self.assertEqual([m.contenido for m in Mensaje.conversacion(a, b)], ["1", "2"])


class AvisoTests(TestCase):
    def test_un_docente_ajeno_no_puede_publicar_en_el_paralelo(self):
        dueno, otro = f.docente(), f.docente()
        aviso = Aviso(paralelo=f.paralelo(dueno), docente=otro, titulo="Hola", mensaje="Texto")
        with self.assertRaises(ValidationError):
            aviso.publicar()

    def test_el_docente_del_paralelo_si_puede_publicar(self):
        d = f.docente()
        aviso = Aviso(paralelo=f.paralelo(d), docente=d, titulo="Hola", mensaje="Texto").publicar()
        self.assertIsNotNone(aviso.pk)


class ParticipanteTests(TestCase):
    def setUp(self):
        d = f.docente()
        self.sesion = SesionClase.objects.create(paralelo=f.paralelo(d), fecha="2026-11-02")
        self.usuario = f.estudiante().usuario

    def test_reingresar_conserva_el_primer_ingreso_y_borra_la_salida(self):
        p = SesionParticipante.registrar_ingreso(self.sesion, self.usuario)
        primer_ingreso = p.hora_ingreso
        p.registrar_salida()
        self.assertIsNotNone(p.hora_salida)
        p2 = SesionParticipante.registrar_ingreso(self.sesion, self.usuario)
        self.assertEqual(p2.pk, p.pk)
        self.assertEqual(p2.hora_ingreso, primer_ingreso)
        self.assertIsNone(p2.hora_salida)
        self.assertEqual(SesionParticipante.objects.count(), 1)

    def test_registrar_salida_dos_veces_no_cambia_la_hora(self):
        p = SesionParticipante.registrar_ingreso(self.sesion, self.usuario)
        p.registrar_salida()
        primera = p.hora_salida
        p.registrar_salida()
        self.assertEqual(p.hora_salida, primera)