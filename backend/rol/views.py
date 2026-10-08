from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect
from usuarios.models import Usuario

USUARIOS_POR_PAGINA = 10
ROLES_FILTRO = {
    '': 'todos',
    'administrador': 'administradores',
    'docente': 'docentes',
    'estudiante': 'estudiantes',
}


# ============================================================
# DASHBOARDS
# ============================================================

def admin_dashboard(request):
    """Dashboard del administrador"""
    if request.session.get('usuario_rol', '').lower() != 'administrador':
        return redirect('login')

    base = Usuario.objects.select_related('rol')

    # Contadores: una sola consulta sobre toda la tabla (no dependen del filtro)
    stats = base.aggregate(
        activos=Count('pk', filter=Q(estado=True)),
        inactivos=Count('pk', filter=Q(estado=False)),
        docentes=Count('pk', filter=Q(estado=True, rol__nombre__iexact='docente')),
        estudiantes=Count('pk', filter=Q(estado=True, rol__nombre__iexact='estudiante')),
    )

    # Filtros
    rol = request.GET.get('rol', '').lower()
    if rol not in ROLES_FILTRO:
        rol = ''
    estado = request.GET.get('estado', '')

    usuarios = base.order_by('-fecha_registro')
    if rol:
        usuarios = usuarios.filter(rol__nombre__iexact=rol)
    if estado == 'activo':
        usuarios = usuarios.filter(estado=True)
    elif estado == 'inactivo':
        usuarios = usuarios.filter(estado=False)

    # Paginación
    paginator = Paginator(usuarios, USUARIOS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_range = [
        n if n != paginator.ELLIPSIS else None
        for n in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
    ]

    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'admin_panel/dashboard.html', {
        'page_obj': page_obj,
        'page_range': page_range,
        'querystring': params.urlencode(),
        'rol_filtro': rol,
        'estado_filtro': estado,
        'active_sub': ROLES_FILTRO[rol],
        'cursos_activos': 0,   # conectar cuando exista el modelo de cursos
        **stats,
    })


def docente_dashboard(request):
    """Dashboard del docente"""
    if request.session.get('usuario_rol', '').lower() != 'docente':
        return redirect('login')
    return render(request, 'docente/dashboard.html')


def estudiante_dashboard(request):
    """Dashboard del estudiante"""
    if request.session.get('usuario_rol', '').lower() != 'estudiante':
        return redirect('login')
    return render(request, 'estudiante/dashboard.html')


# ============================================================
# GESTIÓN DE ROLES (aquí irán las vistas futuras)
# ============================================================

# def lista_roles(request):
#     ...
# def crear_rol(request):
#     ...
# def editar_rol(request, rol_id):
#     ...
# def eliminar_rol(request, rol_id):
#     ...