from django.urls import path
from . import views

urlpatterns = [
    path('',                         views.lista_ordenes, name='lista_ordenes'),
    path('crear/',                    views.crear_orden,   name='crear_orden'),
    path('<int:id_orden>/',           views.detalle_orden, name='detalle_orden'),
    path('<int:id_orden>/estado/',    views.cambiar_estado, name='cambiar_estado_orden'),
    path('productos-proveedor/<int:id_proveedor>/', views.productos_proveedor_json, name='productos_proveedor_json'),
    path('<int:id_orden>/editar/', views.editar_orden, name='editar_orden'),
    path('<int:id_orden>/pdf/', views.exportar_pdf_orden, name='exportar_pdf_orden'),
]