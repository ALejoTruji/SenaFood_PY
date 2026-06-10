from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .models import OrdenCompra, DetalleOrdenCompra
from gestion.models import Usuario, Producto
from proveedor.models import Proveedor


def sesion_requerida(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'usuario_id' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_admin(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get('usuario_rol') != 'Administrador':
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@sesion_requerida
@solo_admin
def lista_ordenes(request):
    filtro_estado   = request.GET.get('estado', '')
    filtro_proveedor = request.GET.get('proveedor', '')

    ordenes = OrdenCompra.objects.select_related('id_proveedor', 'id_usuario').all()

    if filtro_estado:
        ordenes = ordenes.filter(estado=filtro_estado)
    if filtro_proveedor:
        ordenes = ordenes.filter(id_proveedor=filtro_proveedor)

    proveedores = Proveedor.objects.filter(es_activo=True).order_by('nombre')

    return render(request, 'ordencompra/lista.html', {
        'ordenes':           ordenes,
        'proveedores':       proveedores,
        'total_pendientes':  OrdenCompra.objects.filter(estado='pendiente').count(),
        'total_enviadas':    OrdenCompra.objects.filter(estado='enviada').count(),
        'total_recibidas':   OrdenCompra.objects.filter(estado='recibida').count(),
        'total_cerradas':    OrdenCompra.objects.filter(estado='cerrada').count(),
        'filtro_estado':     filtro_estado,
        'filtro_proveedor':  filtro_proveedor,
        'nombre_usuario':    request.session.get('usuario_nombre', ''),
        'rol_usuario':       request.session.get('usuario_rol', ''),
    })

@sesion_requerida
@solo_admin
def crear_orden(request):
    from producto.models import ProveedorProducto
    proveedores = Proveedor.objects.filter(es_activo=True).order_by('nombre')

    # Proveedor preseleccionado desde detalle_proveedor
    proveedor_id = request.GET.get('proveedor', '')
    productos_proveedor = []

    if proveedor_id:
        productos_proveedor = ProveedorProducto.objects.filter(
            proveedor_id=proveedor_id,
            es_activo=True
        ).select_related('producto')

    if request.method == 'POST':
        id_proveedor  = request.POST.get('id_proveedor')
        observaciones = request.POST.get('observaciones', '')
        ids_producto  = request.POST.getlist('producto_id[]')
        cantidades    = request.POST.getlist('cantidad[]')
        precios       = request.POST.getlist('precio_unitario[]')

        if not id_proveedor or not ids_producto:
            messages.error(request, 'Selecciona un proveedor y al menos un producto.')
            return render(request, 'ordencompra/crear.html', {
                'proveedores':       proveedores,
                'productos_proveedor': productos_proveedor,
                'proveedor_id':      id_proveedor,
                'nombre_usuario':    request.session.get('usuario_nombre', ''),
                'rol_usuario':       request.session.get('usuario_rol', ''),
            })

        proveedor = get_object_or_404(Proveedor, pk=id_proveedor)
        usuario   = Usuario.objects.get(id_usuario=request.session['usuario_id'])

        orden = OrdenCompra.objects.create(
            id_proveedor  = proveedor,
            id_usuario    = usuario,
            observaciones = observaciones,
            estado        = 'pendiente',
            total         = 0,
        )

        total = 0
        for i, pid in enumerate(ids_producto):
            try:
                producto = Producto.objects.get(pk=pid)
                cantidad = int(cantidades[i])
                precio   = float(precios[i])
                subtotal = cantidad * precio
                total   += subtotal
                DetalleOrdenCompra.objects.create(
                    orden           = orden,
                    producto        = producto,
                    nombre_producto = producto.nombre,
                    cantidad        = cantidad,
                    precio_unitario = precio,
                    subtotal        = subtotal,
                )
            except Exception:
                continue

        orden.total = total
        orden.save()

        messages.success(request, f'Orden #{orden.id_orden} creada exitosamente.')
        return redirect('detalle_orden', id_orden=orden.id_orden)

    return render(request, 'ordencompra/crear.html', {
        'proveedores':         proveedores,
        'productos_proveedor': productos_proveedor,
        'proveedor_id':        proveedor_id,
        'nombre_usuario':      request.session.get('usuario_nombre', ''),
        'rol_usuario':         request.session.get('usuario_rol', ''),
    })

@sesion_requerida
@solo_admin
def detalle_orden(request, id_orden):
    orden    = get_object_or_404(OrdenCompra, pk=id_orden)
    detalles = DetalleOrdenCompra.objects.filter(orden=orden).select_related('producto')

    return render(request, 'ordencompra/detalle.html', {
        'orden':          orden,
        'detalles':       detalles,
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    request.session.get('usuario_rol', ''),
    })


@sesion_requerida
@solo_admin
def cambiar_estado(request, id_orden):
    orden = get_object_or_404(OrdenCompra, pk=id_orden)

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        estados_validos = ['pendiente', 'enviada', 'recibida', 'cerrada']

        if nuevo_estado in estados_validos:
            orden.estado = nuevo_estado
            orden.save()

            if nuevo_estado == 'enviada' and orden.id_proveedor.email:
                enviar_correo_proveedor(orden)
                messages.success(request, f'Orden #{orden.id_orden} enviada al proveedor por correo.')

            elif nuevo_estado == 'recibida':
                # Sumar al inventario
                detalles = DetalleOrdenCompra.objects.filter(orden=orden).select_related('producto')
                for d in detalles:
                    producto = d.producto
                    producto.stock = (producto.stock or 0) + d.cantidad
                    if producto.estado == 'agotado':
                        producto.estado = 'activo'
                    producto.save()
                messages.success(request, f'Orden #{orden.id_orden} recibida. Stock actualizado para {detalles.count()} productos.')

            else:
                messages.success(request, f'Estado actualizado a {nuevo_estado}.')

    return redirect('detalle_orden', id_orden=id_orden)


def enviar_correo_proveedor(orden):
    detalles = DetalleOrdenCompra.objects.filter(orden=orden)

    filas = ''.join([
        f"""<tr>
            <td style="padding:8px 12px; border-bottom:1px solid #f0f0f0;">{d.nombre_producto}</td>
            <td style="padding:8px 12px; border-bottom:1px solid #f0f0f0; text-align:center;">{d.cantidad}</td>
            <td style="padding:8px 12px; border-bottom:1px solid #f0f0f0; text-align:right;">${d.precio_unitario:,.0f}</td>
            <td style="padding:8px 12px; border-bottom:1px solid #f0f0f0; text-align:right;">${d.subtotal:,.0f}</td>
        </tr>"""
        for d in detalles
    ])

    observaciones_html = f"<p style='color:#666;font-size:13px;background:#f9f9f9;padding:12px;border-radius:6px;'><strong>Observaciones:</strong> {orden.observaciones}</p>" if orden.observaciones else ""

    html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head><meta charset="UTF-8"></head>
        <body style="margin:0;padding:0;background:#f0f4f0;font-family:Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f0;padding:40px 0;">
            <tr><td align="center">
            <table width="600" cellpadding="0" cellspacing="0"
                    style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <tr>
                <td style="background:#28a745;padding:30px;text-align:center;">
                    <h1 style="margin:0;color:#ffffff;font-size:22px;">SenaFood</h1>
                    <p style="margin:6px 0 0;color:#c8f7d0;font-size:13px;">Orden de Compra #{orden.id_orden}</p>
                </td>
                </tr>
                <tr>
                <td style="padding:32px 40px;">
                    <p style="color:#444;font-size:15px;">Estimado(a) <strong>{orden.id_proveedor.nombre}</strong>,</p>
                    <p style="color:#444;font-size:15px;">
                    Nos complace enviarle la siguiente orden de compra.
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0"
                        style="border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;margin:20px 0;">
                    <thead>
                        <tr style="background:#f0fff4;">
                        <th style="padding:10px 12px;text-align:left;color:#555;font-size:13px;">Producto</th>
                        <th style="padding:10px 12px;text-align:center;color:#555;font-size:13px;">Cantidad</th>
                        <th style="padding:10px 12px;text-align:right;color:#555;font-size:13px;">Precio unit.</th>
                        <th style="padding:10px 12px;text-align:right;color:#555;font-size:13px;">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>{filas}</tbody>
                    <tfoot>
                        <tr style="background:#f9fff9;">
                        <td colspan="3" style="padding:12px;text-align:right;font-weight:700;color:#333;">Total:</td>
                        <td style="padding:12px;text-align:right;font-weight:700;color:#28a745;font-size:1.1rem;">
                            ${orden.total:,.0f}
                        </td>
                        </tr>
                    </tfoot>
                    </table>
                    {observaciones_html}
                    <hr style="border:none;border-top:1px solid #e8e8e8;margin:24px 0;">
                    <p style="color:#aaa;font-size:12px;text-align:center;">
                    © 2026 SenaFood
                    </p>
                </td>
                </tr>
            </table>
            </td></tr>
        </table>
        </body>
        </html>
        """

    texto = f"Orden de Compra #{orden.id_orden} — Total: ${orden.total:,.0f}"

    correo = EmailMultiAlternatives(
        subject    = f'Orden de Compra #{orden.id_orden} — SenaFood',
        body       = texto,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to         = [orden.id_proveedor.email],
    )
    correo.attach_alternative(html, "text/html")
    correo.send(fail_silently=False)

@sesion_requerida
@solo_admin
def productos_proveedor_json(request, id_proveedor):
    from producto.models import ProveedorProducto
    from django.http import JsonResponse

    pps = ProveedorProducto.objects.filter(
        proveedor_id=id_proveedor,
        es_activo=True
    ).select_related('producto')

    productos = [
        {
            'id':     pp.producto.id_producto,
            'nombre': pp.producto.nombre,
            'precio': float(pp.precio_proveedor or pp.producto.costo_unitario or 0),
        }
        for pp in pps
    ]

    return JsonResponse({'productos': productos})