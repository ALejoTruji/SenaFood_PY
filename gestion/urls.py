from django.urls import path
from . import views

urlpatterns = [
    path('', views.bienvenida_view, name='bienvenida'),
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'), # <--- Solo esta para salir
    path('perfil/', views.perfil_view, name='perfil'),
    path('cambiar-password/', views.cambiar_password_view, name='cambiar_password'),
    path('solicitar-reset/', views.solicitar_reset_view, name='solicitar_reset'),
    path('restablecer-password/<uuid:token>/', views.restablecer_password_view, name='restablecer_password'),
    path('contacto/', views.contacto_view, name='contacto'),
    path('tienda/toggle/', views.toggle_tienda_view, name='toggle_tienda'),
    path('nosotros/', views.nosotros_view, name='nosotros'),
]