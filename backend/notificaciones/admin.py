from django.contrib import admin
from .models import Notificacion

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "mensaje", "leida", "fecha")
    list_filter = ("tipo", "leida")
