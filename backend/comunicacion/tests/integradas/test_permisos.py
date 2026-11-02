from django.test import TestCase

from comunicacion.permisos import pueden_conversar

from comunicacion.tests import factories as f


class PuedenConversarTests(TestCase):
    def test_nadie_puede_escribirse_a_si_mismo(self):
        d, e = f.docente(), f.estudiante()
        self.assertFalse(pueden_conversar(d.pk, d.pk))
        self.assertFalse(pueden_conversar(e.pk, e.pk))

    def test_docente_con_docente(self):
        self.assertTrue(pueden_conversar(f.docente().pk, f.docente().pk))

    def test_estudiante_con_estudiante_aunque_no_compartan_paralelo(self):
        self.assertTrue(pueden_conversar(f.estudiante().pk, f.estudiante().pk))

    def test_docente_y_estudiante_en_ambos_sentidos_aunque_no_sea_su_alumno(self):
        d, e = f.docente(), f.estudiante()
        self.assertTrue(pueden_conversar(d.pk, e.pk))
        self.assertTrue(pueden_conversar(e.pk, d.pk))

    def test_un_usuario_inactivo_no_puede_chatear_ni_recibir(self):
        activo = f.estudiante()
        inactivo = f.estudiante(estado=False)
        self.assertFalse(pueden_conversar(activo.pk, inactivo.pk))
        self.assertFalse(pueden_conversar(inactivo.pk, activo.pk))

    def test_el_administrador_queda_fuera_del_chat(self):
        admin, e = f.administrador(), f.estudiante()
        self.assertFalse(pueden_conversar(admin.pk, e.pk))
        self.assertFalse(pueden_conversar(e.pk, admin.pk))

    def test_un_id_que_no_existe_no_es_valido(self):
        self.assertFalse(pueden_conversar(f.estudiante().pk, 999999))