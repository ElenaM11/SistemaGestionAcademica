# ============================================================
# IMPORTS
# ============================================================

# Librerías estándar de Python
import re
import secrets
import time
import unicodedata

# Django: atajos y utilidades
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# Modelos locales
from rol.models import Rol
from .models import Usuario, Estudiante, Docente


# ============================================================
# CONSTANTES
# ============================================================

DOMINIO = 'davinci.edu.bo'
CRED_TTL = 15 * 60  # las credenciales pendientes caducan a los 15 minutos


# ============================================================
# UTILIDADES PARA GENERAR CÓDIGO Y CORREO
# ============================================================

def _inicial(texto):
    """Primera letra A-Z (sin tildes) de un texto; '' si no hay."""
    limpio = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()
    m = re.search(r'[A-Za-z]', limpio)
    return m.group(0).upper() if m else ''


def generar_codigo_estudiante(nombres, ap_pat, ap_mat):
    """Ej.: Quispe Mamani, Mariela -> QMM001. Usa solo los datos disponibles."""
    primer_nombre = (nombres or '').strip().split(' ')[0]
    prefijo = ''.join(_inicial(x) for x in (ap_pat, ap_mat, primer_nombre))
    if not prefijo:
        return ''
    existentes = Estudiante.objects.filter(
        codigo_estudiante__startswith=prefijo
    ).values_list('codigo_estudiante', flat=True)
    numeros = [int(c[len(prefijo):]) for c in existentes if c[len(prefijo):].isdigit()]
    return f'{prefijo}{(max(numeros) + 1 if numeros else 1):03d}'


def correo_desde_codigo(codigo):
    """Convierte un código de estudiante en correo. Ej: QMM001 -> qmm001@davinci.edu.bo"""
    return f'{codigo.lower()}@{DOMINIO}' if codigo else ''


def generar_password(n=10):
    """Ej.: K7mP2$xQ9a. Sin caracteres ambiguos (0/O, 1/l/I)."""
    mayus, minus = 'ABCDEFGHJKLMNPQRSTUVWXYZ', 'abcdefghijkmnopqrstuvwxyz'
    digitos, simbolos = '23456789', '$#@%*!?'
    chars = [secrets.choice(mayus), secrets.choice(minus),
             secrets.choice(digitos), secrets.choice(simbolos)]
    todos = mayus + minus + digitos + simbolos
    chars += [secrets.choice(todos) for _ in range(n - 4)]
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


def api_codigo_estudiante(request):
    """Vista previa en tiempo real para el formulario (AJAX)."""
    if request.session.get('usuario_rol', '').lower() != 'administrador':
        return JsonResponse({'error': 'forbidden'}, status=403)
    codigo = generar_codigo_estudiante(
        request.GET.get('nombres'), request.GET.get('ap_pat'), request.GET.get('ap_mat'))
    return JsonResponse({'codigo': codigo, 'correo': correo_desde_codigo(codigo)})


# ============================================================
# UTILIDADES INTERNAS
# ============================================================

def _es_admin(request):
    """Devuelve True si el usuario logueado es administrador."""
    return request.session.get('usuario_rol', '').lower() == 'administrador'


def _usuario_actual(request):
    """Devuelve el Usuario logueado o None si no hay sesión."""
    uid = request.session.get('usuario_id')
    return Usuario.objects.filter(id_usuario=uid).first() if uid else None


def _form_registro(request, datos=None):
    """Renderiza el formulario de registro (con o sin datos previos)."""
    return render(request, 'admin_panel/register_user.html',
                  {'roles': Rol.objects.all(), 'datos': datos})


def _guardar_credenciales(request, usuario, password, titulo):
    """Guarda las credenciales en la sesión para mostrarlas una sola vez."""
    rol = usuario.rol.nombre
    nombre = f'{usuario.nombres} {usuario.ap_pat}'.strip()
    request.session['credenciales_nuevas'] = {
        'titulo': titulo.format(nombre=nombre),
        'nombre': f'{usuario.nombres} {usuario.ap_pat} {usuario.ap_mat}'.strip(),
        'rol': rol,
        'correo': usuario.correo,
        'password': password,
        'aviso1': f'Comparte estos datos con el {rol.lower()}.',
        'aviso2': f'El {rol.lower()} deberá cambiar la contraseña al primer inicio de sesión.',
        'creado': time.time(),
    }
# AUTENTICACIÓN
def login_view(request):
    """Vista de inicio de sesión."""
    if request.method == 'POST':
        correo = request.POST.get('correo')
        password = request.POST.get('password')
        try:
            usuario = Usuario.objects.get(correo=correo, estado=True)
        except Usuario.DoesNotExist:
            messages.error(request, 'Correo o contraseña incorrectos')
            return render(request, 'accounts/login.html')
        resultado = check_password(password, usuario.password_hash)
        if resultado:
            # Guardamos datos en la sesión
            request.session['usuario_id'] = usuario.id_usuario
            request.session['usuario_nombre'] = f"{usuario.nombres} {usuario.ap_pat}"
            request.session['usuario_rol'] = usuario.rol.nombre
            request.session['usuario_iniciales'] = (usuario.nombres[:1] + usuario.ap_pat[:1]).upper()
            request.session['debe_cambiar_password'] = usuario.debe_cambiar_password
            # Si el admin lo obligó a cambiar contraseña, lo mandamos ahí primero
            if usuario.debe_cambiar_password:
                return redirect('cambiar_password')
            # Redirigir según el rol
            rol = usuario.rol.nombre.lower()
            if rol == 'administrador':
                return redirect('admin_dashboard')
            elif rol == 'docente':
                return redirect('docente_dashboard')
            elif rol == 'estudiante':
                return redirect('estudiante_dashboard')
            else:
                messages.error(request, 'Rol no reconocido')
                return render(request, 'accounts/login.html')
        else:
            messages.error(request, 'Correo o contraseña incorrectos')
            return render(request, 'accounts/login.html')
    return render(request, 'accounts/login.html')


def logout_view(request):
    """Vista de cierre de sesión."""
    request.session.flush()
    return redirect('login')


# ============================================================
# REGISTRO DE USUARIOS (solo admin)
# ============================================================

def admin_register_user(request):
    """Vista para que el admin registre nuevos usuarios."""
    if not _es_admin(request):
        messages.error(request, 'No tienes permisos para acceder aquí')
        return redirect('login')
    if request.method != 'POST':
        return _form_registro(request)
    p = request.POST
    nombres, ap_pat, ap_mat = p.get('nombres', '').strip(), p.get('ap_pat', '').strip(), p.get('ap_mat', '').strip()
    ci, telefono = p.get('ci', '').strip(), p.get('telefono', '').strip()
    try:
        rol = Rol.objects.get(pk=p.get('rol'))
    except (Rol.DoesNotExist, ValueError):
        messages.error(request, 'Rol inválido')
        return _form_registro(request, p)
    rol_nombre = rol.nombre.lower()
    # Validaciones de unicidad
    if Usuario.objects.filter(ci=ci).exists():
        messages.error(request, 'Ya existe un usuario con ese carnet de identidad')
        return _form_registro(request, p)
    if Usuario.objects.filter(telefono=telefono).exists():
        messages.error(request, 'Ya existe un usuario con ese número de teléfono')
        return _form_registro(request, p)
    # Validaciones específicas por rol
    if rol_nombre == 'estudiante':
        if not all(p.get(c, '').strip() for c in ('fecha_nacimiento', 'contacto_emergencia', 'telefono_emergencia')):
            messages.error(request, 'Completa los datos del estudiante y de su contacto de emergencia')
            return _form_registro(request, p)
    elif rol_nombre == 'docente' and not p.get('especialidad', '').strip():
        messages.error(request, 'Indica la especialidad del docente')
        return _form_registro(request, p)
    # El sistema genera la contraseña
    password = generar_password()
    # Crear usuario (reintenta si choca el código)
    for _ in range(3):
        try:
            with transaction.atomic():
                if rol_nombre == 'estudiante':
                    codigo = generar_codigo_estudiante(nombres, ap_pat, ap_mat)
                    correo = correo_desde_codigo(codigo)
                else:
                    correo = p.get('correo', '').strip().lower()
                    if Usuario.objects.filter(correo=correo).exists():
                        messages.error(request, 'Ya existe un usuario con ese correo')
                        return _form_registro(request, p)

                usuario = Usuario.objects.create(
                    nombres=nombres, ap_pat=ap_pat, ap_mat=ap_mat, ci=ci,
                    correo=correo, telefono=telefono, rol=rol,
                    password_hash=make_password(password),
                    debe_cambiar_password=True,
                )
                if rol_nombre == 'estudiante':
                    Estudiante.objects.create(
                        usuario=usuario, codigo_estudiante=codigo,
                        fecha_nacimiento=p['fecha_nacimiento'],
                        contacto_emergencia=p['contacto_emergencia'].strip(),
                        telefono_emergencia=p['telefono_emergencia'].strip(),
                    )
                elif rol_nombre == 'docente':
                    Docente.objects.create(usuario=usuario, especialidad=p['especialidad'].strip())
            break
        except IntegrityError:
            continue
    else:
        messages.error(request, 'No se pudo registrar el usuario. Intenta de nuevo.')
        return _form_registro(request, p)

    _guardar_credenciales(request, usuario, password, 'Usuario {nombre} registrado correctamente.')
    return redirect('admin_credenciales')


# ============================================================
# CREDENCIALES (mostrar una sola vez)
# ============================================================

def admin_credenciales(request):
    """Muestra las credenciales del último usuario creado."""
    if not _es_admin(request):
        return redirect('login')
    cred = request.session.get('credenciales_nuevas')
    if not cred or time.time() - cred.get('creado', 0) > CRED_TTL:
        request.session.pop('credenciales_nuevas', None)
        messages.info(request, 'No hay credenciales pendientes por mostrar.')
        return redirect('admin_dashboard')
    return render(request, 'admin_panel/credenciales.html', {'cred': cred})


@require_POST
def admin_credenciales_limpiar(request):
    """Borra las credenciales de la sesión (AJAX)."""
    if not _es_admin(request):
        return JsonResponse({'ok': False}, status=403)
    request.session.pop('credenciales_nuevas', None)
    return JsonResponse({'ok': True})


# ============================================================
# EDITAR, ESTADO Y RESTABLECER CONTRASEÑA
# ============================================================

def admin_edit_user(request, id_usuario):
    """Vista para editar los datos de un usuario."""
    if not _es_admin(request):
        return redirect('login')
    u = get_object_or_404(Usuario.objects.select_related('rol'), id_usuario=id_usuario)
    rol_nombre = u.rol.nombre.lower()
    est = Estudiante.objects.filter(usuario=u).first() if rol_nombre == 'estudiante' else None
    doc = Docente.objects.filter(usuario=u).first() if rol_nombre == 'docente' else None
    es_propio = u.id_usuario == request.session.get('usuario_id')

    inicial = {
        'nombres': u.nombres, 'ap_pat': u.ap_pat, 'ap_mat': u.ap_mat,
        'ci': u.ci or '', 'correo': u.correo, 'telefono': u.telefono or '',
        'estado': '1' if u.estado else '0',
        'especialidad': doc.especialidad if doc and doc.especialidad else '',
        'fecha_nacimiento': est.fecha_nacimiento.isoformat() if est and est.fecha_nacimiento else '',
        'contacto_emergencia': (est.contacto_emergencia or '') if est else '',
        'telefono_emergencia': (est.telefono_emergencia or '') if est else '',
    }

    def mostrar(form):
        return render(request, 'admin_panel/edit_user.html', {
            'usuario': u, 'form': form, 'es_estudiante': est is not None or rol_nombre == 'estudiante',
            'es_docente': rol_nombre == 'docente', 'es_propio': es_propio,
            'codigo_estudiante': est.codigo_estudiante if est else '',
        })

    if request.method != 'POST':
        return mostrar(inicial)

    p = request.POST
    nombres, ap_pat, ap_mat = p.get('nombres', '').strip(), p.get('ap_pat', '').strip(), p.get('ap_mat', '').strip()
    ci, telefono = p.get('ci', '').strip(), p.get('telefono', '').strip()
    correo = u.correo if rol_nombre == 'estudiante' else p.get('correo', '').strip().lower()
    estado = u.estado if es_propio else (p.get('estado') == '1')

    if Usuario.objects.filter(ci=ci).exclude(id_usuario=u.id_usuario).exists():
        messages.error(request, 'Ya existe otro usuario con ese carnet de identidad')
        return mostrar(p)
    if Usuario.objects.filter(telefono=telefono).exclude(id_usuario=u.id_usuario).exists():
        messages.error(request, 'Ya existe otro usuario con ese número de teléfono')
        return mostrar(p)
    if Usuario.objects.filter(correo=correo).exclude(id_usuario=u.id_usuario).exists():
        messages.error(request, 'Ya existe otro usuario con ese correo')
        return mostrar(p)

    with transaction.atomic():
        u.nombres, u.ap_pat, u.ap_mat = nombres, ap_pat, ap_mat
        u.ci, u.telefono, u.correo, u.estado = ci, telefono, correo, estado
        u.save()
        if doc:
            doc.especialidad = p.get('especialidad', '').strip()
            doc.save()
        if est:
            est.fecha_nacimiento = p.get('fecha_nacimiento') or None
            est.contacto_emergencia = p.get('contacto_emergencia', '').strip()
            est.telefono_emergencia = p.get('telefono_emergencia', '').strip()
            est.save()

    if es_propio:
        request.session['usuario_nombre'] = f'{u.nombres} {u.ap_pat}'
        request.session['usuario_iniciales'] = (u.nombres[:1] + u.ap_pat[:1]).upper()
    messages.success(request, f'Datos de {nombres} actualizados correctamente.')
    return redirect('admin_dashboard')


@require_POST
def admin_toggle_estado(request, id_usuario):
    """Activa o desactiva un usuario (AJAX)."""
    if not _es_admin(request):
        return JsonResponse({'ok': False, 'error': 'Sin permisos'}, status=403)
    if id_usuario == request.session.get('usuario_id'):
        return JsonResponse({'ok': False, 'error': 'No puedes desactivar tu propia cuenta.'}, status=400)
    u = get_object_or_404(Usuario, id_usuario=id_usuario)
    u.estado = request.POST.get('estado') == '1'
    u.save(update_fields=['estado'])
    return JsonResponse({'ok': True, 'estado': u.estado})


@require_POST
def admin_reset_password(request, id_usuario):
    """Genera una nueva contraseña para el usuario y la muestra."""
    if not _es_admin(request):
        return redirect('login')
    u = get_object_or_404(Usuario.objects.select_related('rol'), id_usuario=id_usuario)
    password = generar_password()
    u.password_hash = make_password(password)
    u.debe_cambiar_password = True
    u.save(update_fields=['password_hash', 'debe_cambiar_password'])
    _guardar_credenciales(request, u, password, 'Contraseña de {nombre} restablecida correctamente.')
    return redirect('admin_credenciales')


# ============================================================
# CAMBIO DE CONTRASEÑA Y PERFIL
# ============================================================

def _validar_password_segura(password, usuario=None):
    """Valida que la contraseña cumpla con los requisitos mínimos."""

    # ⬇️ PRIMERO: validar que no sea una contraseña común
    comunes = ['12345678', 'password', 'qwerty123', 'admin123', '123456789', 'password123']
    if password.lower() in comunes:
        return False, 'Esa contraseña es demasiado común. Elige otra.'

    # ⬇️ DESPUÉS: las demás validaciones
    if len(password) < 8:
        return False, 'La contraseña debe tener al menos 8 caracteres.'
    if not re.search(r'[A-Z]', password):
        return False, 'La contraseña debe tener al menos una letra mayúscula.'
    if not re.search(r'[a-z]', password):
        return False, 'La contraseña debe tener al menos una letra minúscula.'
    if not re.search(r'\d', password):
        return False, 'La contraseña debe tener al menos un número.'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-]', password):
        return False, 'La contraseña debe tener al menos un símbolo (!@#$%^&*).'

    if usuario:
        if usuario.nombres and usuario.nombres.lower() in password.lower():
            return False, 'La contraseña no debe contener tu nombre.'
        if usuario.ap_pat and usuario.ap_pat.lower() in password.lower():
            return False, 'La contraseña no debe contener tu apellido.'

    return True, ''


def cambiar_password(request):
    """Vista para que el usuario cambie su contraseña."""
    u = _usuario_actual(request)
    if not u:
        return redirect('login')

    if request.method == 'POST':
        actual = request.POST.get('actual', '')
        nueva = request.POST.get('nueva', '')
        conf = request.POST.get('confirmar', '')

        if not check_password(actual, u.password_hash):
            messages.error(request, 'La contraseña actual no es correcta.')
        elif nueva != conf:
            messages.error(request, 'Las contraseñas nuevas no coinciden.')
        elif nueva == actual:
            messages.error(request, 'La nueva contraseña debe ser distinta a la actual.')
        else:
            es_valida, error = _validar_password_segura(nueva, u)
            if not es_valida:
                messages.error(request, error)
            else:
                u.password_hash = make_password(nueva)
                u.debe_cambiar_password = False
                u.save()
                request.session['debe_cambiar_password'] = False
                messages.success(request, 'Contraseña actualizada correctamente.')
                return redirect('perfil')

    return render(request, 'accounts/cambiar_password.html', {
        'forzado': u.debe_cambiar_password
    })


# Sidebars por rol (para reutilizar en la vista de perfil)
SIDEBARS = {
    'docente': 'components/sidebar_docente.html',
    'estudiante': 'components/sidebar_estudiante.html',
    'administrador': 'components/sidebar_admin.html',
}


def perfil(request):
    """Vista para ver el perfil del usuario logueado."""
    u = _usuario_actual(request)
    if not u:
        return redirect('login')

    rol = u.rol.nombre.lower()
    extra = []

    if rol == 'estudiante':
        est = Estudiante.objects.filter(usuario=u).first()
        if est:
            extra = [('Código de estudiante', est.codigo_estudiante)]
    elif rol == 'docente':
        doc = Docente.objects.filter(usuario=u).first()
        if doc:
            extra = [('Especialidad', doc.especialidad)]

    return render(request, 'accounts/perfil.html', {
        'es_admin': rol == 'administrador',
        'sidebar_template': SIDEBARS.get(rol),
        'nombre_completo': f'{u.nombres} {u.ap_pat} {u.ap_mat}'.strip(),
        'correo': u.correo,
        'rol_nombre': u.rol.nombre,
        'iniciales': (u.nombres[:1] + u.ap_pat[:1]).upper(),
        'extra': extra,
    })
