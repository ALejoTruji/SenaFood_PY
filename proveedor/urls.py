from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_proveedores_view, name='lista_proveedores'),
    path('crear/', views.crear_proveedor_view, name='crear_proveedor'),
    path('editar/<int:id>/', views.editar_proveedor_view, name='editar_proveedor'),
    path('eliminar/<int:id>/', views.eliminar_proveedor_view, name='eliminar_proveedor'),
    path('detalle/<int:id>/', views.detalle_proveedor_view, name='detalle_proveedor'),
    path('exportar/excel/', views.exportar_excel_proveedores, name='exportar_excel_proveedores'),
    path('exportar/pdf/', views.exportar_pdf_proveedores, name='exportar_pdf_proveedores'),
    path('<int:id>/asignar-producto/',              views.asignar_producto_proveedor,   name='asignar_producto_proveedor'),
    path('<int:id>/desasignar-producto/<int:id_pp>/', views.desasignar_producto_proveedor, name='desasignar_producto_proveedor'),
]