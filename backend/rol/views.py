from django.shortcuts import render

def login_view(request):
    return render(request, 'accounts/login.html')

def logout_view(request):
    return render(request, 'accounts/login.html')  # temporal

def admin_dashboard(request):
    return render(request, 'admin_panel/dashboard.html')

def admin_register_user(request):
    return render(request, 'admin_panel/register_user.html')

def docente_dashboard(request):
    return render(request, 'docente/dashboard.html')

def estudiante_dashboard(request):
    return render(request, 'estudiante/dashboard.html')