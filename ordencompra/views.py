from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db import transaction
from .models import OrdenCompra, DetalleOrdenCompra
from gestion.models import Usuario, Producto
from proveedor.models import Proveedor

import os
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image as RLImage
)


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
    proveedores = Proveedor.objects.filter(es_activo=True).order_by('nombre')

    # Proveedor preseleccionado desde la URL (si aplica)
    proveedor_id = request.GET.get('proveedor', '')
    
    # Cargamos todos los productos del sistema para la vista inicial
    productos_sistema = Producto.objects.all().order_by('nombre')

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
                'productos_sistema': productos_sistema,
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
        'productos_sistema':   productos_sistema,
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
def exportar_pdf_orden(request, id_orden):
    """
    Genera la orden de compra en PDF, formato factura (vertical), con los datos
    de SenaFOOD como empresa emisora, los datos del proveedor y el detalle de productos.
    """
    orden    = get_object_or_404(OrdenCompra, pk=id_orden)
    detalles = DetalleOrdenCompra.objects.filter(orden=orden).select_related('producto')

    # ── Datos fijos de la empresa emisora ──
    EMPRESA = {
        'nombre':    'SenaFOOD',
        'nit':       '800900500-1',
        'direccion': 'Calle 65 # 13 - 68',
        'telefono':  '4555544',
    }

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        'Title', parent=styles['Title'], fontSize=18,
        textColor=colors.HexColor('#28A745'), fontName='Helvetica-Bold',
        alignment=1, spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'], fontSize=9,
        textColor=colors.HexColor('#666666'), alignment=1,
    )
    label_style = ParagraphStyle(
        'Label', parent=styles['Normal'], fontSize=8.5,
        textColor=colors.HexColor('#888888'),
    )
    value_style = ParagraphStyle(
        'Value', parent=styles['Normal'], fontSize=10,
        textColor=colors.HexColor('#222222'), fontName='Helvetica-Bold',
        spaceAfter=2,
    )

    # ── Encabezado: logo + nombre de la empresa ──
    logo_path = os.path.join(settings.BASE_DIR, 'gestion', 'static', 'gestion', 'img', 'logo.png')
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=60, height=60)
        header_data = [[
            logo,
            Paragraph(
                f"<b>{EMPRESA['nombre']}</b><br/>"
                f"NIT: {EMPRESA['nit']}<br/>"
                f"{EMPRESA['direccion']}<br/>"
                f"Tel: {EMPRESA['telefono']}",
                ParagraphStyle('EmpresaInfo', parent=styles['Normal'], fontSize=9,
                                textColor=colors.HexColor('#444444'), leading=12),
            ),
            Paragraph(
                f"<b>ORDEN DE COMPRA</b><br/>"
                f"N° {orden.id_orden:06d}<br/>"
                f"Fecha: {orden.fecha.strftime('%d/%m/%Y')}",
                ParagraphStyle('OrdenInfo', parent=styles['Normal'], fontSize=9,
                                textColor=colors.HexColor('#28A745'), alignment=2, leading=12),
            ),
        ]]
        header_table = Table(header_data, colWidths=[70, 280, 180])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph(EMPRESA['nombre'], title_style))
        elements.append(Paragraph(f"Orden de Compra N° {orden.id_orden:06d}", subtitle_style))

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#28A745')))
    elements.append(Spacer(1, 14))

    # ── Datos del proveedor ──
    proveedor = orden.id_proveedor
    proveedor_data = [[
        Paragraph('<b>PROVEEDOR</b>', label_style),
    ], [
        Paragraph(proveedor.nombre or '—', value_style),
    ], [
        Paragraph(f"NIT: {proveedor.nit or '—'}", subtitle_style),
    ], [
        Paragraph(f"Email: {proveedor.email or '—'}", subtitle_style),
    ], [
        Paragraph(f"Teléfono: {proveedor.telefono or '—'}", subtitle_style),
    ], [
        Paragraph(f"Dirección: {proveedor.direccion or '—'}", subtitle_style),
    ]]
    proveedor_table = Table(proveedor_data, colWidths=[530])
    proveedor_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fff9')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#a8d5b5')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(proveedor_table)
    elements.append(Spacer(1, 6))

    # ── Creada por / estado ──
    creado_por = f"{orden.id_usuario.nombre} {orden.id_usuario.apellido}" if orden.id_usuario else '—'
    info_data = [[
        Paragraph(f"<b>Creada por:</b> {creado_por}", subtitle_style),
        Paragraph(f"<b>Estado:</b> {orden.get_estado_display()}", subtitle_style),
    ]]
    info_table = Table(info_data, colWidths=[265, 265])
    elements.append(info_table)
    elements.append(Spacer(1, 14))

    # ── Observaciones ──
    if orden.observaciones:
        obs_style = ParagraphStyle('Obs', parent=styles['Normal'], fontSize=9,
                                    textColor=colors.HexColor('#444444'))
        obs_table = Table(
            [[Paragraph(f"<b>Observaciones:</b> {orden.observaciones}", obs_style)]],
            colWidths=[530],
        )
        obs_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffbea')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#ffe9a8')),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(obs_table)
        elements.append(Spacer(1, 14))

    # ── Tabla de productos ──
    data = [['#', 'Producto', 'Cantidad', 'Precio unit.', 'Subtotal']]
    for i, d in enumerate(detalles, 1):
        data.append([
            str(i),
            d.nombre_producto,
            str(d.cantidad),
            f'${float(d.precio_unitario):,.0f}',
            f'${float(d.subtotal):,.0f}',
        ])

    tabla = Table(data, repeatRows=1, colWidths=[25, 230, 70, 100, 105])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28A745')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fff4')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#a8d5b5')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(tabla)
    elements.append(Spacer(1, 4))

    # ── Total ──
    total_data = [[
        Paragraph('<b>TOTAL</b>', ParagraphStyle('TotalLabel', parent=styles['Normal'],
                                                    fontSize=11, alignment=2)),
        Paragraph(f"<b>${float(orden.total):,.0f}</b>",
                    ParagraphStyle('TotalValue', parent=styles['Normal'], fontSize=13,
                                    textColor=colors.HexColor('#28A745'), alignment=2)),
    ]]
    total_table = Table(total_data, colWidths=[425, 105])
    total_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#28A745')),
    ]))
    elements.append(total_table)

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawString(2 * cm, 1 * cm, 'SenaFOOD - Orden de Compra')
        canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f'Página {doc_.page}')
        canvas.setStrokeColor(colors.HexColor('#28A745'))
        canvas.setLineWidth(1)
        canvas.line(2 * cm, 1.3 * cm, A4[0] - 2 * cm, 1.3 * cm)
        canvas.restoreState()

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return HttpResponse(
        buffer, content_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="OrdenCompra_{orden.id_orden:06d}.pdf"'},
    )


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
    """
    Retorna SIEMPRE la lista completa de todos los productos creados en el sistema,
    ignorando las restricciones de asignación por proveedor.
    """
    pps = Producto.objects.all().order_by('nombre')

    productos = [
        {
            'id':     pp.id_producto,
            'nombre': pp.nombre,
            'precio': float(getattr(pp, 'costo_unitario', 0) or getattr(pp, 'precio', 0) or 0),
        }
        for pp in pps
    ]

    return JsonResponse({'productos': productos})


@sesion_requerida
@solo_admin
def editar_orden(request, id_orden):
    """
    Vista optimizada para modificar las cantidades, precios u observaciones de una orden de compra.
    Implementa transacciones atómicas para blindar el borrado y la reescritura de filas.
    """
    orden = get_object_or_404(OrdenCompra, pk=id_orden)
    
    if orden.estado in ['recibida', 'cerrada']:
        messages.error(request, f'La Orden #{orden.id_orden} ya fue {orden.estado} y no se puede modificar.')
        return redirect('detalle_orden', id_orden=orden.id_orden)

    productos_sistema = Producto.objects.all().order_by('nombre')
    detalles_actuales = DetalleOrdenCompra.objects.filter(orden=orden).select_related('producto')

    if request.method == 'POST':
        observaciones = request.POST.get('observaciones', '')
        ids_producto  = request.POST.getlist('producto_id[]')
        cantidades    = request.POST.getlist('cantidad[]')
        # CAMBIO CLAVE: Cambiado de 'precio_unitario[]' a 'precio[]' para coincidir exactamente con el name del HTML
        precios       = request.POST.getlist('precio[]') 

        if not ids_producto or len(ids_producto) == 0:
            messages.error(request, 'La orden no puede quedar vacía. Selecciona al menos un producto.')
            return redirect('editar_orden', id_orden=orden.id_orden)

        try:
            # Usamos transacciones para asegurar que si algo falla, no se pierdan los ítems anteriores
            with transaction.atomic():
                orden.observaciones = observaciones
                
                # 1. Limpiamos el detalle anterior de manera segura
                DetalleOrdenCompra.objects.filter(orden=orden).delete()

                # 2. Reconstruimos los detalles con las filas del POST
                total = 0
                for i, pid in enumerate(ids_producto):
                    if not pid:  # Omitir filas que no tengan un producto seleccionado
                        continue
                        
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

                # 3. Guardamos el total final recalculado
                orden.total = total
                orden.save()

            messages.success(request, f'Orden #{orden.id_orden} modificada correctamente.')
            return redirect('detalle_orden', id_orden=orden.id_orden)

        except Exception as e:
            messages.error(request, f'Ocurrió un error al guardar los cambios: {str(e)}')
            return redirect('editar_orden', id_orden=orden.id_orden)

    return render(request, 'ordencompra/editar.html', {
        'orden':             orden,
        'detalles':          detalles_actuales,
        'productos_sistema': productos_sistema,
        'nombre_usuario':    request.session.get('usuario_nombre', ''),
        'rol_usuario':       request.session.get('usuario_rol', ''),
    })