from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect
from usuarios.models import Usuario
from cursos.models import Curso

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

    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    base = Usuario.objects.select_related('rol')

    # Contadores: solo en la carga completa de la página (la búsqueda en vivo no los muestra)
    stats = {} if es_ajax else base.aggregate(
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

    # Búsqueda: cada palabra debe aparecer en nombre, apellidos, correo, CI o código de estudiante
    q = request.GET.get('q', '').strip()[:100]
    for palabra in q.split():
        usuarios = usuarios.filter(
            Q(nombres__icontains=palabra)
            | Q(ap_pat__icontains=palabra)
            | Q(ap_mat__icontains=palabra)
            | Q(correo__icontains=palabra)
            | Q(ci__icontains=palabra)
            | Q(estudiante__codigo_estudiante__icontains=palabra)
        )

    # Paginación
    paginator = Paginator(usuarios, USUARIOS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_range = [
        n if n != paginator.ELLIPSIS else None
        for n in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
    ]

    params = request.GET.copy()
    params.pop('page', None)

    contexto = {
        'page_obj': page_obj,
        'page_range': page_range,
        'querystring': params.urlencode(),
        'rol_filtro': rol,
        'estado_filtro': estado,
        'q': q,
        'active_sub': ROLES_FILTRO[rol],
        'cursos_activos': Curso.objects.filter(activo=True).count(),
        **stats,
    }

    # Búsqueda en vivo / paginador: se devuelve solo la tabla
    plantilla = 'admin_panel/_usuarios_tabla.html' if es_ajax else 'admin_panel/dashboard.html'
    return render(request, plantilla, contexto)


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
