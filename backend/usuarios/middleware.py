from django.shortcuts import redirect
from django.urls import reverse


class ForzarCambioPasswordMiddleware:
    """Si el usuario debe cambiar su contraseña, solo puede ver esa pantalla y cerrar sesión."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.session.get('debe_cambiar_password'):
            permitidas = {reverse('cambiar_password'), reverse('logout')}
            if request.path not in permitidas and not request.path.startswith('/static/'):
                return redirect('cambiar_password')
        return self.get_response(request)