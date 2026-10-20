from django.contrib import admin
from .models import Actividad, Entrega


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("titulo", "paralelo", "tipo", "fecha_limite", "estado")
    list_filter = ("tipo", "estado", "paralelo")
    search_fields = ("titulo",)


@admin.register(Entrega)
class EntregaAdmin(admin.ModelAdmin):
    list_display = ("actividad", "estudiante", "estado", "calificacion", "es_tardia")
    list_filter = ("estado", "es_tardia")
