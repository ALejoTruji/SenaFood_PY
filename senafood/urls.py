from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls), 
    path('', include('gestion.urls')), #ruta para gestion 
    path('usuarios/', include('usuarios.urls')), # ruta para usuarios
    path('pqrsf/', include('pqrs.urls')),# ruta de pqrsf
    path('notificaciones/', include('notificaciones.urls')), # ruta notificaciones
    path('proveedores/', include('proveedor.urls')), # ruta proveedores
    path('productos/', include('producto.urls')),#ruta producto
    path('inventario/', include('inventario.urls')),#ruta inventario
    path('catalogo/', include('catalogo.urls')),
    path('ventas/', include('ventas.urls')),
    path('ordencompra/', include('ordencompra.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)