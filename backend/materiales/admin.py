from django.contrib import admin
from .models import Material

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("titulo", "paralelo", "tipo", "fecha_publicacion")
    list_filter = ("tipo", "paralelo")
    search_fields = ("titulo",)
