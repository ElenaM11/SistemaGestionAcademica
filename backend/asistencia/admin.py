from django.contrib import admin
from .models import Asistencia, SesionClase

@admin.register(SesionClase)
class SesionClaseAdmin(admin.ModelAdmin):
    list_display = ("paralelo", "fecha", "hora_inicio", "estado")
    list_filter = ("estado", "paralelo")
@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("sesion", "estudiante", "estado", "registrado_por")
    list_filter = ("estado",)
