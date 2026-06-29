from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from gestion.models import Producto, Carrito, Detallecarrito, Usuario
from datetime import date
from django.db import models
from django.contrib import messages
import hashlib
import hmac
import json
import os
import requests as http_requests
from django.views.decorators.csrf import csrf_exempt


def sesion_requerida(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'usuario_id' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_usuario(request):
    try:
        return Usuario.objects.get(id_usuario=request.session['usuario_id'])
    except Usuario.DoesNotExist:
        return None


def get_carrito_activo(usuario):
    # Si hay múltiples carritos abiertos (no debería pasar),
    # tomar el más reciente y cerrar los demás
    carritos = Carrito.objects.filter(
        usuario=usuario,
        estado='abierto'
    ).order_by('-create_at')

    if carritos.count() > 1:
        # Mantener solo el más reciente, marcar los demás como cancelados
        carrito_activo = carritos.first()
        carritos.exclude(pk=carrito_activo.pk).update(estado='cancelado')
        return carrito_activo
    elif carritos.count() == 1:
        return carritos.first()
    else:
        # No hay carrito abierto, crear uno nuevo
        carrito = Carrito.objects.create(
            usuario=usuario,
            estado='abierto',
            total=0
        )
        return carrito

# ─────────────────────────────────────────
# CATÁLOGO
# ─────────────────────────────────────────
@sesion_requerida
def catalogo_view(request):
    from gestion.models import ConfiguracionTienda
    config = ConfiguracionTienda.get()
    tienda_abierta = bool(config.tienda_abierta)

    filtro_categoria = request.GET.get('categoria', '')
    filtro_buscar    = request.GET.get('buscar', '')

    productos = Producto.objects.filter(
        estado='activo',
        es_activo=True
    ).order_by('nombre')

    if filtro_categoria:
        productos = productos.filter(categoria=filtro_categoria)
    if filtro_buscar:
        productos = productos.filter(nombre__icontains=filtro_buscar)

    categorias = Producto.objects.filter(
        estado='activo', es_activo=True
    ).values_list('categoria', flat=True).distinct().exclude(
        categoria__isnull=True
    ).exclude(categoria='').order_by('categoria')

    usuario  = get_usuario(request)
    carrito  = get_carrito_activo(usuario)
    n_items  = Detallecarrito.objects.filter(id_carrito=carrito).count()

    return render(request, 'catalogo/catalogo.html', {
        'productos':         productos,
        'categorias':        categorias,
        'filtro_categoria':  filtro_categoria,
        'filtro_buscar':     filtro_buscar,
        'n_items':           n_items,
        'nombre_usuario':    request.session.get('usuario_nombre', ''),
        'rol_usuario':       request.session.get('usuario_rol', ''),
        'tienda_abierta':    tienda_abierta,
    })


# ─────────────────────────────────────────
# AGREGAR AL CARRITO
# ─────────────────────────────────────────
@sesion_requerida
def agregar_carrito(request, id_producto):
    from gestion.models import ConfiguracionTienda

    config = ConfiguracionTienda.get()
    if not bool(config.tienda_abierta) and request.session.get('usuario_rol') == 'Cliente':
        messages.error(request, 'La tienda está cerrada. No puedes agregar productos al carrito.')
        return redirect('catalogo')

    producto = get_object_or_404(Producto, pk=id_producto, estado='activo', es_activo=True)
    usuario  = get_usuario(request)
    carrito  = get_carrito_activo(usuario)

    if (producto.stock or 0) <= 0:
        messages.error(request, f'"{producto.nombre}" no tiene stock disponible.')
        return redirect('catalogo')

    precio = producto.precio_promocion if producto.en_promocion else producto.precio_venta or producto.costo_unitario

    detalle, creado = Detallecarrito.objects.get_or_create(
        id_carrito  = carrito,
        id_producto = producto,
        defaults    = {'cantidad': 1, 'precio_unitario': precio}
    )

    if not creado:
        if detalle.cantidad >= (producto.stock or 0):
            messages.error(request, f'No hay más stock disponible de "{producto.nombre}". Stock máximo: {producto.stock}.')
            return redirect('catalogo')
        detalle.cantidad += 1
        detalle.save()

    detalles = Detallecarrito.objects.filter(id_carrito=carrito)
    total    = sum(d.cantidad * d.precio_unitario for d in detalles)
    carrito.total     = total
    carrito.update_at = timezone.now()
    carrito.save()

    messages.success(request, f'"{producto.nombre}" agregado al carrito.')
    return redirect('catalogo')


# ─────────────────────────────────────────
# CONTADOR CARRITO (AJAX)
# ─────────────────────────────────────────
@sesion_requerida
def contador_carrito(request):
    usuario = get_usuario(request)
    carrito = get_carrito_activo(usuario)
    n_items = Detallecarrito.objects.filter(id_carrito=carrito).count()
    return JsonResponse({'total': n_items})


# ─────────────────────────────────────────
# VER CARRITO
# ─────────────────────────────────────────
@sesion_requerida
def ver_carrito(request):
    usuario  = get_usuario(request)
    carrito  = get_carrito_activo(usuario)
    detalles = Detallecarrito.objects.filter(
        id_carrito=carrito
    ).select_related('id_producto')

    total = sum(d.cantidad * d.precio_unitario for d in detalles)

    return render(request, 'catalogo/carrito.html', {
        'carrito':        carrito,
        'detalles':       detalles,
        'total':          total,
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    request.session.get('usuario_rol', ''),
    })


# ─────────────────────────────────────────
# ACTUALIZAR CANTIDAD
# ─────────────────────────────────────────
@sesion_requerida
def actualizar_cantidad(request, id_detalle):
    if request.method == 'POST':
        detalle  = get_object_or_404(Detallecarrito, pk=id_detalle)
        cantidad = int(request.POST.get('cantidad', 1))

        if cantidad <= 0:
            detalle.delete()
        else:
            detalle.cantidad = cantidad
            detalle.save()

        carrito  = detalle.id_carrito
        detalles = Detallecarrito.objects.filter(id_carrito=carrito)
        total    = sum(d.cantidad * d.precio_unitario for d in detalles)
        carrito.total = total
        carrito.save()

    return redirect('ver_carrito')


# ─────────────────────────────────────────
# ELIMINAR DETALLE
# ─────────────────────────────────────────
@sesion_requerida
def eliminar_detalle(request, id_detalle):
    detalle = get_object_or_404(Detallecarrito, pk=id_detalle)
    carrito = detalle.id_carrito
    detalle.delete()

    detalles = Detallecarrito.objects.filter(id_carrito=carrito)
    total    = sum(d.cantidad * d.precio_unitario for d in detalles)
    carrito.total = total
    carrito.save()

    return redirect('ver_carrito')


# ─────────────────────────────────────────
# CONFIRMAR PEDIDO (cliente)
# ─────────────────────────────────────────
@sesion_requerida
def confirmar_pedido(request):
    usuario = get_usuario(request)
    carrito = get_carrito_activo(usuario)

    detalles = Detallecarrito.objects.filter(id_carrito=carrito).select_related('id_producto')

    if not detalles.exists():
        messages.error(request, 'Tu carrito está vacío.')
        return redirect('ver_carrito')

    errores = []
    for d in detalles:
        stock_disponible = d.id_producto.stock or 0
        if d.cantidad > stock_disponible:
            errores.append(
                f'"{d.id_producto.nombre}" — solicitaste {d.cantidad} pero solo hay {stock_disponible} disponibles.'
            )

    if errores:
        for error in errores:
            messages.error(request, error)
        return redirect('ver_carrito')

    metodo = request.POST.get('metodo_pago', 'efectivo')

    carrito.fecha_confirmacion = timezone.now()
    carrito.update_at          = timezone.now()

    if metodo == 'nequi':
        carrito.estado     = 'pendiente_pago'
        carrito.metodopago = 'nequi'
        carrito.save()
        return redirect('pago_nequi_cliente', id_carrito=carrito.id_carrito)
    elif metodo == 'daviplata':
        carrito.estado     = 'pendiente_pago'
        carrito.metodopago = 'daviplata'
        carrito.save()
        return redirect('pago_daviplata_cliente', id_carrito=carrito.id_carrito)
    else:
        carrito.estado     = 'pendiente_pago'
        carrito.metodopago = 'efectivo'
        carrito.save()
        return redirect('pedido_confirmado')


# ─────────────────────────────────────────
# PEDIDO CONFIRMADO (cliente)
# ─────────────────────────────────────────
@sesion_requerida
def pedido_confirmado(request):
    return render(request, 'catalogo/confirmado.html', {
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    request.session.get('usuario_rol', ''),
    })


# ═══════════════════════════════════════════════════════════
# WOMPI — INTEGRACIÓN DE PAGOS AUTOMÁTICOS
# ═══════════════════════════════════════════════════════════

def _generar_firma_integridad(reference, amount_in_cents, currency):
    """Genera la firma SHA256 requerida por Wompi para integridad."""
    integrity_secret = os.environ.get('WOMPI_INTEGRITY_SECRET', '')
    cadena = f'{reference}{amount_in_cents}{currency}{integrity_secret}'
    return hashlib.sha256(cadena.encode()).hexdigest()


def _aprobar_pedido(carrito):
    """
    Marca el pedido como pagado y notifica al cliente.
    Usado tanto por el webhook como por la pantalla de retorno.
    """
    from notificaciones.models import Notificacion

    if carrito.estado == 'pendiente_entrega':
        return  # Ya fue procesado anteriormente

    carrito.estado    = 'pendiente_entrega'
    carrito.update_at = timezone.now()
    carrito.save()

    Notificacion.objects.create(
        usuario = carrito.usuario,
        tipo    = 'carrito',
        mensaje = f'¡Tu pedido #{carrito.id_carrito} esta en preparacion! Acércate a recogerlo.',
        carrito = carrito,
    )


def _construir_url_wompi(carrito, metodo):
    """
    Construye la URL del checkout de Wompi con todos los parámetros.
    metodo: 'NEQUI' o 'DAVIPLATA'
    """
    public_key      = os.environ.get('WOMPI_PUBLIC_KEY', '')
    amount_in_cents = int(carrito.total * 100)
    reference       = f'SENAFOOD-{carrito.id_carrito}'
    currency        = 'COP'
    redirect_url    = f'https://senafood-production.up.railway.app/catalogo/wompi/retorno/?carrito={carrito.id_carrito}'
    firma           = _generar_firma_integridad(reference, amount_in_cents, currency)

    # Guardar la referencia en el carrito para rastrear el pago
    carrito.numerofactura = reference
    carrito.save()

    url = (
        f'https://checkout.wompi.co/p/'
        f'?public-key={public_key}'
        f'&currency={currency}'
        f'&amount-in-cents={amount_in_cents}'
        f'&reference={reference}'
        f'&signature:integrity={firma}'
        f'&redirect-url={redirect_url}'
        f'&payment-methods[]=NEQUI'
        f'&payment-methods[]=DAVIPLATA'
        f'&payment-methods[]=PSE'
    )
    return url


@sesion_requerida
def pago_nequi_cliente(request, id_carrito):
    """Redirige al checkout de Wompi preseleccionando Nequi."""
    carrito = get_object_or_404(Carrito, pk=id_carrito)

    # Verificar que el carrito pertenece al usuario de la sesión
    usuario = get_usuario(request)
    if carrito.usuario != usuario:
        return redirect('ver_carrito')

    public_key      = os.environ.get('WOMPI_PUBLIC_KEY', '')
    amount_in_cents = int(carrito.total * 100)
    reference       = f'SENAFOOD-{carrito.id_carrito}'
    currency        = 'COP'
    redirect_url    = f'https://senafood-production.up.railway.app/catalogo/wompi/retorno/?carrito={carrito.id_carrito}'
    firma           = _generar_firma_integridad(reference, amount_in_cents, currency)

    carrito.numerofactura = reference
    carrito.save()

    # Si no hay llave pública configurada, mostrar pantalla manual de respaldo
    if not public_key:
        return render(request, 'catalogo/pago_nequi_cliente.html', {
            'carrito':        carrito,
            'valor':          int(carrito.total or 0),
            'nombre_usuario': request.session.get('usuario_nombre', ''),
            'rol_usuario':    request.session.get('usuario_rol', ''),
        })

    url_wompi = (
        f'https://checkout.wompi.co/p/'
        f'?public-key={public_key}'
        f'&currency={currency}'
        f'&amount-in-cents={amount_in_cents}'
        f'&reference={reference}'
        f'&signature:integrity={firma}'
        f'&redirect-url={redirect_url}'
    )
    return redirect(url_wompi)


@sesion_requerida
def pago_daviplata_cliente(request, id_carrito):
    """Redirige al checkout de Wompi preseleccionando Daviplata."""
    carrito = get_object_or_404(Carrito, pk=id_carrito)

    usuario = get_usuario(request)
    if carrito.usuario != usuario:
        return redirect('ver_carrito')

    public_key      = os.environ.get('WOMPI_PUBLIC_KEY', '')
    amount_in_cents = int(carrito.total * 100)
    reference       = f'SENAFOOD-{carrito.id_carrito}'
    currency        = 'COP'
    redirect_url    = f'https://senafood-production.up.railway.app/catalogo/wompi/retorno/?carrito={carrito.id_carrito}'
    firma           = _generar_firma_integridad(reference, amount_in_cents, currency)

    carrito.numerofactura = reference
    carrito.save()

    if not public_key:
        return render(request, 'catalogo/pago_daviplata_cliente.html', {
            'carrito':        carrito,
            'valor':          int(carrito.total or 0),
            'nombre_usuario': request.session.get('usuario_nombre', ''),
            'rol_usuario':    request.session.get('usuario_rol', ''),
        })

    url_wompi = (
        f'https://checkout.wompi.co/p/'
        f'?public-key={public_key}'
        f'&currency={currency}'
        f'&amount-in-cents={amount_in_cents}'
        f'&reference={reference}'
        f'&signature:integrity={firma}'
        f'&redirect-url={redirect_url}'
    )
    return redirect(url_wompi)


@sesion_requerida
def wompi_retorno(request):
    """
    Wompi redirige aquí después de que el usuario completa el pago.
    Verificamos el estado consultando la API de Wompi directamente.
    """
    id_carrito = request.GET.get('carrito')
    if not id_carrito:
        return redirect('ver_carrito')

    carrito = get_object_or_404(Carrito, pk=id_carrito)

    # Si el webhook ya procesó el pago, redirigir directamente
    if carrito.estado == 'pendiente_entrega':
        return redirect('pedido_confirmado')

    # Consultar el estado en la API de Wompi por referencia
    private_key = os.environ.get('WOMPI_PRIVATE_KEY', '')
    referencia  = f'SENAFOOD-{carrito.id_carrito}'

    try:
        resp = http_requests.get(
            f'https://sandbox.wompi.co/v1/transactions?reference={referencia}',
            headers={'Authorization': f'Bearer {private_key}'},
            timeout=10,
        )
        if resp.status_code == 200:
            transacciones = resp.json().get('data', [])
            for t in transacciones:
                if t.get('status') == 'APPROVED':
                    _aprobar_pedido(carrito)
                    return redirect('pedido_confirmado')
    except Exception:
        pass

    # Pago pendiente o en proceso
    messages.info(
        request,
        'Tu pago está siendo procesado. Te notificaremos cuando se confirme. '
        'Puedes revisar el estado en tus notificaciones.'
    )
    return redirect('ver_carrito')


@csrf_exempt
def wompi_webhook(request):
    """
    Endpoint que Wompi llama automáticamente cuando cambia el estado de un pago.
    No requiere sesión de usuario — viene directamente de los servidores de Wompi.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload     = json.loads(request.body)
        evento      = payload.get('event', '')
        datos       = payload.get('data', {})
        transaccion = datos.get('transaction', {})
        timestamp   = payload.get('timestamp', '')
        checksum    = payload.get('signature', {}).get('checksum', '')

        # Verificar firma del evento para evitar llamadas falsas
        events_secret  = os.environ.get('WOMPI_EVENTS_SECRET', '')
        firma_esperada = hashlib.sha256(
            f'{timestamp}{events_secret}'.encode()
        ).hexdigest()

        if not hmac.compare_digest(checksum, firma_esperada):
            return HttpResponse('Firma inválida', status=401)

        # Solo procesar cuando el pago es aprobado
        if evento == 'transaction.updated' and transaccion.get('status') == 'APPROVED':
            referencia = transaccion.get('reference', '')
            if referencia.startswith('SENAFOOD-'):
                id_carrito = int(referencia.replace('SENAFOOD-', ''))
                try:
                    carrito = Carrito.objects.get(pk=id_carrito)
                    _aprobar_pedido(carrito)
                except Carrito.DoesNotExist:
                    pass

        return HttpResponse(status=200)

    except Exception:
        return HttpResponse(status=400)


# Vistas de confirmación manual — se mantienen como respaldo
# por si Wompi no está disponible o para pagos en efectivo
@sesion_requerida
def confirmar_pago_nequi(request, id_carrito):
    carrito = get_object_or_404(Carrito, pk=id_carrito)
    if request.method == 'POST':
        _aprobar_pedido(carrito)
    return redirect('pedido_confirmado')


@sesion_requerida
def confirmar_pago_daviplata(request, id_carrito):
    carrito = get_object_or_404(Carrito, pk=id_carrito)
    if request.method == 'POST':
        _aprobar_pedido(carrito)
    return redirect('pedido_confirmado')


# ─────────────────────────────────────────
# VISTA VENDEDOR
# ─────────────────────────────────────────
@sesion_requerida
def vista_vendedor(request):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Vendedor', 'Administrador', 'Cajero']:
        return redirect('dashboard')

    pedidos_caja = Carrito.objects.filter(
        estado='pendiente_pago'
    ).prefetch_related('detallecarrito_set__id_producto').order_by('create_at')

    pedidos_entrega = Carrito.objects.filter(
        estado='pendiente_entrega'
    ).prefetch_related('detallecarrito_set__id_producto').order_by('create_at')

    return render(request, 'catalogo/vendedor.html', {
        'pedidos_caja':    pedidos_caja,
        'pedidos_entrega': pedidos_entrega,
        'nombre_usuario':  request.session.get('usuario_nombre', ''),
        'rol_usuario':     request.session.get('usuario_rol', ''),
    })


# ─────────────────────────────────────────
# REGISTRAR PAGO (cajero)
# ─────────────────────────────────────────
@sesion_requerida
def registrar_pago(request, id_carrito):
    from notificaciones.models import Notificacion
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Vendedor', 'Administrador', 'Cajero']:
        return redirect('dashboard')

    carrito = get_object_or_404(Carrito, pk=id_carrito, estado='pendiente_pago')
    carrito.estado     = 'pendiente_entrega'
    carrito.metodopago = 'efectivo'
    carrito.update_at  = timezone.now()
    carrito.save()

    Notificacion.objects.create(
        usuario = carrito.usuario,
        tipo    = 'carrito',
        mensaje = f'¡Tu pedido #{carrito.id_carrito} se está preparando! Acércate a recogerlo.',
        carrito = carrito,
    )

    messages.success(request, f"¡Pedido #{id_carrito} cobrado! Ya puedes entregar el producto.")
    return redirect('vista_cajero')


# ─────────────────────────────────────────
# Notificar stock bajo
# ─────────────────────────────────────────
def notificar_stock_bajo(producto):
    from notificaciones.models import Notificacion
    from inventario.models import Inventario

    try:
        inv = Inventario.objects.get(idproducto=producto.id_producto)
        alerta_min = inv.alerta_minimos
    except Inventario.DoesNotExist:
        alerta_min = 5

    if (producto.stock or 0) <= alerta_min:
        admins = Usuario.objects.filter(
            rol__nombre_rol='Administrador',
            es_activo=True
        )
        for admin in admins:
            ya_notificado = Notificacion.objects.filter(
                usuario=admin,
                tipo='stock',
                leida=False,
                mensaje__icontains=producto.nombre
            ).exists()

            if not ya_notificado:
                Notificacion.objects.create(
                    usuario = admin,
                    tipo    = 'stock',
                    mensaje = f'Stock bajo: "{producto.nombre}" tiene {producto.stock} unidades (mínimo: {alerta_min})',
                )


# ─────────────────────────────────────────
# CONFIRMAR ENTREGA
# ─────────────────────────────────────────
@sesion_requerida
def confirmar_entrega(request, id_carrito):
    from notificaciones.models import Notificacion
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Vendedor', 'Administrador', 'Cajero']:
        return redirect('dashboard')

    carrito  = get_object_or_404(Carrito, pk=id_carrito, estado='pendiente_entrega')
    detalles = Detallecarrito.objects.filter(id_carrito=carrito)

    for d in detalles:
        producto       = d.id_producto
        producto.stock = max(0, (producto.stock or 0) - d.cantidad)

        if producto.stock <= 0:
            producto.estado = 'agotado'
        elif producto.fecha_vencimiento and producto.fecha_vencimiento < date.today():
            producto.estado = 'vencido'
        else:
            producto.estado = 'activo'

        producto.update_at = timezone.now()
        producto.save()

        notificar_stock_bajo(producto)

    carrito.estado        = 'entregado'
    carrito.fecha_entrega = timezone.now()
    carrito.update_at     = timezone.now()
    carrito.save()

    Notificacion.objects.create(
        usuario = carrito.usuario,
        tipo    = 'carrito',
        mensaje = f'¡Gracias por tu compra #{carrito.id_carrito}! Esperamos verte pronto. ¿Cómo fue tu experiencia?',
        carrito = carrito,
    )

    return redirect('vista_vendedor')


@sesion_requerida
def pedidos_json(request):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Vendedor', 'Administrador', 'Cajero']:
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    pedidos_caja = []
    for pedido in Carrito.objects.filter(estado='pendiente_pago').order_by('create_at'):
        detalles = []
        for d in Detallecarrito.objects.filter(id_carrito=pedido).select_related('id_producto'):
            detalles.append({
                'nombre':   d.id_producto.nombre,
                'cantidad': d.cantidad,
                'subtotal': float(d.cantidad * d.precio_unitario),
            })
        pedidos_caja.append({
            'id':         pedido.id_carrito,
            'cliente':    f'{pedido.usuario.nombre} {pedido.usuario.apellido}',
            'total':      float(pedido.total or 0),
            'detalles':   detalles,
            'metodopago': pedido.metodopago or 'efectivo',
        })

    pedidos_entrega = []
    for pedido in Carrito.objects.filter(estado='pendiente_entrega').order_by('create_at'):
        detalles = []
        for d in Detallecarrito.objects.filter(id_carrito=pedido).select_related('id_producto'):
            detalles.append({
                'nombre':   d.id_producto.nombre,
                'cantidad': d.cantidad,
                'subtotal': float(d.cantidad * d.precio_unitario),
            })
        pedidos_entrega.append({
            'id':         pedido.id_carrito,
            'cliente':    f'{pedido.usuario.nombre} {pedido.usuario.apellido}',
            'total':      float(pedido.total or 0),
            'detalles':   detalles,
            'metodopago': pedido.metodopago or 'efectivo',
        })

    return JsonResponse({
        'pedidos_caja':    pedidos_caja,
        'pedidos_entrega': pedidos_entrega,
    })


@sesion_requerida
def cobrar_pedido(request, id_carrito):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Vendedor', 'Administrador', 'Cajero']:
        return redirect('dashboard')

    carrito  = get_object_or_404(Carrito, pk=id_carrito, estado='pendiente_pago')
    detalles = Detallecarrito.objects.filter(
        id_carrito=carrito
    ).select_related('id_producto')

    return render(request, 'catalogo/cobrar.html', {
        'carrito':        carrito,
        'detalles':       detalles,
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    request.session.get('usuario_rol', ''),
    })


@sesion_requerida
def vista_cajero(request):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Cajero', 'Administrador']:
        return redirect('dashboard')

    import datetime
    hoy = datetime.date.today()

    pedidos_pago = Carrito.objects.filter(
        estado='pendiente_pago'
    ).prefetch_related('detallecarrito_set__id_producto').order_by('create_at')

    historial_hoy = Carrito.objects.filter(
        estado__in=['pendiente_entrega', 'entregado'],
        fecha_confirmacion__date=hoy
    ).prefetch_related('detallecarrito_set__id_producto').order_by('-fecha_confirmacion')

    productos = Producto.objects.filter(
        estado='activo',
        es_activo=True
    ).order_by('nombre')

    total_dia = sum(c.total or 0 for c in historial_hoy)

    return render(request, 'catalogo/cajero.html', {
        'pedidos_pago':    pedidos_pago,
        'historial_hoy':   historial_hoy,
        'productos':       productos,
        'total_dia':       total_dia,
        'nombre_usuario':  request.session.get('usuario_nombre', ''),
        'rol_usuario':     rol,
    })


@sesion_requerida
def cajero_agregar_item(request):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Cajero', 'Administrador']:
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    data       = json.loads(request.body)
    items      = data.get('items', [])
    usuario_id = data.get('usuario_id')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        return JsonResponse({'error': 'Cliente no encontrado'}, status=404)

    carrito = Carrito.objects.create(
        usuario            = usuario,
        estado             = 'pendiente_pago',
        total              = 0,
        fecha_confirmacion = timezone.now(),
    )

    total = 0
    for item in items:
        try:
            producto = Producto.objects.get(pk=item['id'], estado='activo', es_activo=True)
            cantidad = int(item['cantidad'])
            precio   = producto.precio_promocion if producto.en_promocion else producto.precio_venta or producto.costo_unitario
            Detallecarrito.objects.create(
                id_carrito      = carrito,
                id_producto     = producto,
                cantidad        = cantidad,
                precio_unitario = precio,
            )
            total += cantidad * precio
        except Producto.DoesNotExist:
            continue

    carrito.total = total
    carrito.save()

    return JsonResponse({'ok': True, 'carrito_id': carrito.id_carrito, 'total': float(total)})


@sesion_requerida
def buscar_cliente(request):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Cajero', 'Administrador']:
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'clientes': []})

    clientes = Usuario.objects.filter(
        es_activo=True,
        rol__nombre_rol='Cliente'
    ).filter(
        models.Q(nombre__icontains=q) |
        models.Q(apellido__icontains=q) |
        models.Q(email__icontains=q)
    )[:10]

    return JsonResponse({'clientes': [
        {'id': c.id_usuario, 'nombre': f'{c.nombre} {c.apellido}', 'email': c.email}
        for c in clientes
    ]})


@sesion_requerida
def cajero_crear_cliente_rapido(request):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Cajero', 'Administrador']:
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    from django.contrib.auth.hashers import make_password
    from gestion.models import Rol

    data   = json.loads(request.body)
    nombre = data.get('nombre', '').strip()
    cedula = data.get('cedula', '').strip()

    if not nombre or not cedula:
        return JsonResponse({'error': 'Nombre y cédula son obligatorios'}, status=400)

    if Usuario.objects.filter(numero_identificacion=cedula).exists():
        cliente = Usuario.objects.get(numero_identificacion=cedula)
        return JsonResponse({
            'ok':     True,
            'id':     cliente.id_usuario,
            'nombre': f'{cliente.nombre} {cliente.apellido or ""}',
            'existia': True
        })

    try:
        rol_cliente = Rol.objects.get(nombre_rol='Cliente')
    except Rol.DoesNotExist:
        return JsonResponse({'error': 'Rol Cliente no encontrado'}, status=500)

    partes    = nombre.split(' ', 1)
    nombre_us = partes[0]
    apellido  = partes[1] if len(partes) > 1 else ''
    email     = f'caja_{cedula}@senafood.local'

    cliente = Usuario.objects.create(
        nombre                = nombre_us,
        apellido              = apellido,
        email                 = email,
        password              = make_password(cedula),
        numero_identificacion = cedula,
        tipo_identificacion   = 'CC',
        rol                   = rol_cliente,
        es_activo             = True,
    )

    return JsonResponse({
        'ok':     True,
        'id':     cliente.id_usuario,
        'nombre': f'{cliente.nombre} {cliente.apellido}',
        'existia': False
    })


@sesion_requerida
def estado_tienda_json(request):
    from gestion.models import ConfiguracionTienda
    config = ConfiguracionTienda.get()
    return JsonResponse({'tienda_abierta': bool(config.tienda_abierta)})


@sesion_requerida
def cobrar_nequi(request, id_carrito):
    import qrcode
    import base64
    from io import BytesIO

    rol = request.session.get('usuario_rol', '')
    if rol not in ['Vendedor', 'Administrador', 'Cajero']:
        return redirect('dashboard')

    carrito  = get_object_or_404(Carrito, pk=id_carrito, estado='pendiente_pago')
    detalles = Detallecarrito.objects.filter(
        id_carrito=carrito
    ).select_related('id_producto')

    valor      = int(carrito.total or 0)

    # Link de Wompi — en producción cambiar test_VPOS_ictMqt por el ID real
    wompi_link = os.environ.get(
        'WOMPI_LINK',
        'https://checkout.wompi.co/l/test_VPOS_ictMqt'
    )

    # Generar QR del link de Wompi
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(wompi_link)
    qr.make(fit=True)
    img    = qr.make_image(fill_color='#7b2ff7', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'catalogo/cobrar_nequi.html', {
        'carrito':        carrito,
        'detalles':       detalles,
        'wompi_link':     wompi_link,
        'qr_base64':      qr_base64,
        'valor':          valor,
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    rol,
    })


@sesion_requerida
def historial_cliente(request):
    from django.core.paginator import Paginator
    if request.session.get('usuario_rol') != 'Cliente':
        return redirect('dashboard')

    usuario = get_usuario(request)
    pedidos = Carrito.objects.filter(
        usuario=usuario
    ).exclude(estado='abierto').prefetch_related(
        'detallecarrito_set__id_producto'
    ).order_by('-fecha_confirmacion')

    paginator   = Paginator(pedidos, 5)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    return render(request, 'catalogo/historial.html', {
        'pedidos':        page_obj,
        'page_obj':       page_obj,
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    request.session.get('usuario_rol', ''),
    })


@sesion_requerida
def calificar_pedido(request, id_carrito):
    if request.session.get('usuario_rol') != 'Cliente':
        return redirect('dashboard')

    usuario  = get_usuario(request)
    carrito  = get_object_or_404(Carrito, pk=id_carrito, usuario=usuario, estado='entregado')
    detalles = Detallecarrito.objects.filter(
        id_carrito=carrito
    ).select_related('id_producto')

    from gestion.models import Calificacion
    ya_califico = Calificacion.objects.filter(
        carrito=carrito,
        usuario=usuario
    ).exists()

    return render(request, 'catalogo/calificar.html', {
        'carrito':        carrito,
        'detalles':       detalles,
        'ya_califico':    ya_califico,
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    request.session.get('usuario_rol', ''),
    })


@sesion_requerida
def guardar_calificacion(request, id_carrito):
    if request.session.get('usuario_rol') != 'Cliente':
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('historial_cliente')

    from gestion.models import Calificacion
    usuario  = get_usuario(request)
    carrito  = get_object_or_404(Carrito, pk=id_carrito, usuario=usuario, estado='entregado')
    detalles = Detallecarrito.objects.filter(id_carrito=carrito).select_related('id_producto')

    for d in detalles:
        puntuacion = request.POST.get(f'puntuacion_{d.id_producto.id_producto}')
        comentario = request.POST.get(f'comentario_{d.id_producto.id_producto}', '')

        if puntuacion:
            Calificacion.objects.update_or_create(
                usuario  = usuario,
                producto = d.id_producto,
                carrito  = carrito,
                defaults = {
                    'puntuacion': int(puntuacion),
                    'comentario': comentario,
                }
            )

    return redirect('catalogo')


@sesion_requerida
def detalle_pedido(request, id_carrito):
    if request.session.get('usuario_rol') != 'Cliente':
        return redirect('dashboard')

    usuario  = get_usuario(request)
    carrito  = get_object_or_404(Carrito, pk=id_carrito, usuario=usuario)
    detalles = Detallecarrito.objects.filter(
        id_carrito=carrito
    ).select_related('id_producto')

    return render(request, 'catalogo/detalle_pedido.html', {
        'carrito':        carrito,
        'detalles':       detalles,
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    request.session.get('usuario_rol', ''),
    })