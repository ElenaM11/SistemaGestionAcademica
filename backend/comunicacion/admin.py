from django.contrib import admin
from .models import Aviso, Mensaje, SesionParticipante


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "paralelo", "docente", "fecha_publicacion")


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ("emisor", "receptor", "paralelo", "fecha_envio", "leido")
    list_filter = ("leido",)


@admin.register(SesionParticipante)
class SesionParticipanteAdmin(admin.ModelAdmin):
    list_display = ("sesion", "usuario", "hora_ingreso", "hora_salida")
