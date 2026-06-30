from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from .models import Usuario, Rol 
from django.contrib.auth import logout
from django.core.mail import send_mail
from django.conf import settings
import datetime
from .models import TokenRestablecimiento
from django.core.mail import EmailMultiAlternatives
from .models import ConfiguracionTienda

def bienvenida_view(request):
    if 'usuario_id' in request.session:
        return redirect('dashboard')
    return render(request, 'gestion/bienvenida.html')

def login_view(request):
    error_mensaje = None
    email_ingresado = ""

    # Si ya tiene sesión activa, redirigir al dashboard
    if 'usuario_id' in request.session:
        return redirect('dashboard')

    if request.method == 'POST':
        email_ingresado = request.POST.get('email')
        password_ingresada = request.POST.get('password')

        try:
            usuario = Usuario.objects.get(email=email_ingresado)
            if check_password(password_ingresada, usuario.password):
                request.session.flush()
                request.session['usuario_id'] = usuario.id_usuario
                request.session['usuario_nombre'] = usuario.nombre
                request.session['usuario_rol'] = usuario.rol.nombre_rol
                response = redirect('dashboard')
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response['Pragma'] = 'no-cache'
                return response
            else:
                error_mensaje = "Contraseña incorrecta."
        except Usuario.DoesNotExist:
            error_mensaje = "El correo no está registrado."

    response = render(request, 'gestion/login.html', {
        'error': error_mensaje,
        'email_previo': email_ingresado
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


def registro_view(request):
    usuario_id = request.session.get('usuario_id')
    es_admin = False
    
    if usuario_id:
        try:
            usuario_logueado = Usuario.objects.get(id_usuario=usuario_id)
            if usuario_logueado.rol and usuario_logueado.rol.nombre_rol == 'Administrador':
                es_admin = True
        except Usuario.DoesNotExist:
            es_admin = False

    if request.method == 'POST':
        # 1. Recoger datos
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        email = request.POST.get('email')
        num_id = request.POST.get('numero_identificacion')
        id_rol_seleccionado = request.POST.get('rol')

        # --- ESCUDO DE VALIDACIÓN (Evita error 1062) ---
        
        # Validar si el email ya existe
        if Usuario.objects.filter(email=email).exists():
            return render(request, 'gestion/registro.html', {
                'error': f'El correo "{email}" ya está registrado en SenaFood.',
                'nombre': nombre, 'apellido': apellido, 'es_admin': es_admin,
                'roles': Rol.objects.all() if es_admin else None
            })

        # Validar si el número de identificación ya existe
        if Usuario.objects.filter(numero_identificacion=num_id).exists():
            return render(request, 'gestion/registro.html', {
                'error': f'El número de documento "{num_id}" ya está registrado.',
                'nombre': nombre, 'apellido': apellido, 'es_admin': es_admin,
                'roles': Rol.objects.all() if es_admin else None
            })
        
        # -----------------------------------------------

        try:
            # Lógica de asignación de Rol
            if es_admin and id_rol_seleccionado:
                rol_asignado = Rol.objects.get(id_rol=id_rol_seleccionado)
            else:
                rol_asignado, _ = Rol.objects.get_or_create(nombre_rol='Cliente')

            # Guardado de Usuario
            password_segura = make_password(request.POST.get('password'))
            nuevo_usuario = Usuario(
                nombre=nombre,
                apellido=apellido,
                email=email,
                password=password_segura,
                telefono=request.POST.get('telefono'),
                tipo_identificacion=request.POST.get('tipo_identificacion'),
                numero_identificacion=num_id,
                rol=rol_asignado 
            )
            nuevo_usuario.save()
            
            messages.success(request, f"¡Usuario {nuevo_usuario.nombre} registrado correctamente!")
            return redirect('usuarios_lista' if es_admin else 'login')
            
        except Exception as e:
            return render(request, 'gestion/registro.html', {
                'error': f'Error inesperado: {e}',
                'roles': Rol.objects.all() if es_admin else None,
                'es_admin': es_admin
            })
            
    # GET
    contexto = {
        'roles': Rol.objects.all() if es_admin else None,
        'es_admin': es_admin 
    }
    return render(request, 'gestion/registro.html', contexto)

def dashboard_view(request):
    if 'usuario_nombre' not in request.session:
        return redirect('login')

    rol = request.session.get('usuario_rol', '')

    if rol == 'Vendedor':
        return redirect('vista_vendedor')

    if rol == 'Cliente':
        return redirect('catalogo')

    # Solo Administrador ve el dashboard
    return render(request, 'gestion/inicio.html', {
        'nombre_usuario': request.session.get('usuario_nombre', ''),
        'rol_usuario':    rol,
    })
def perfil_view(request):
    if 'usuario_id' not in request.session:
        return redirect('login')
    
    usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])
    
    if request.method == 'POST':
        # 1. Recogemos los datos (Asegúrate de capturar numero_identificacion)
        nuevo_telefono = request.POST.get('telefono')
        nuevo_correo = request.POST.get('email')
        nueva_id = request.POST.get('numero_identificacion') # <--- CLAVE: Capturar este dato
        
        # 2. VALIDACIÓN: Verificar que sean numéricos y no estén vacíos
        if not nuevo_telefono.isdigit() or not nueva_id.isdigit():
            messages.error(request, "El teléfono y la identificación deben contener solo números.")
            return render(request, 'gestion/perfil.html', {'usuario': usuario})

        # 3. Actualizamos el objeto
        usuario.telefono = nuevo_telefono
        usuario.email = nuevo_correo
        usuario.numero_identificacion = nueva_id # <--- Guardar en el campo de tu modelo
        
        usuario.save()
        
        messages.success(request, "Datos actualizados con éxito.")
        return redirect('perfil')

    return render(request, 'gestion/perfil.html', {'usuario': usuario})

def cambiar_password_view(request):
    # 1. Verificación de sesión
    if 'usuario_id' not in request.session:
        return redirect('login')

    # 2. Obtener el usuario siempre (para GET y POST) usando el campo correcto
    try:
        usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])
    except Usuario.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        # 3. Recoger datos con los nombres exactos de tu HTML
        # Nota: Asegúrate que en el HTML los 'name' coincidan con estos
        old_pass = request.POST.get('password_actual') # Antes tenías 'old_password'
        new_pass = request.POST.get('nueva_password')  # Antes tenías 'new_password'
        confirm_pass = request.POST.get('confirmar_password')

        # 4. Validaciones de seguridad
        if not check_password(old_pass, usuario.password):
            messages.error(request, "La contraseña actual es incorrecta.")
            return render(request, 'gestion/cambiar_password.html')
        
        if new_pass != confirm_pass:
            messages.error(request, "Las nuevas contraseñas no coinciden.")
            return render(request, 'gestion/cambiar-password.html')

        if len(new_pass) < 8:
            messages.error(request, "La nueva contraseña debe tener al menos 8 caracteres.")
            return render(request, 'gestion/cambiar-password.html')

        # 5. Guardado seguro
        usuario.password = make_password(new_pass)
        usuario.save()
        
        messages.success(request, "Contraseña actualizada correctamente.")
        return redirect('cambiar_password') # Te sugiero volver al perfil para ver el mensaje de éxito

    return render(request, 'gestion/cambiar_password.html')

def logout_view(request):
    request.session.flush()
    return redirect('login')

# En gestion/views.py

# En gestion/views.py
def lista_usuarios_view(request):
    if 'usuario_id' not in request.session:
        return redirect('login')
    
    usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])
    usuarios = Usuario.objects.all()
    
    return render(request, 'usuarios/lista.html', {
        'usuarios': usuarios,
        'nombre_usuario': usuario.nombre,
    })

def solicitar_reset_view(request):
    mensaje = None
    error = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            usuario = Usuario.objects.get(email=email, es_activo=True)
            # Invalidar tokens anteriores del mismo usuario
            TokenRestablecimiento.objects.filter(usuario=usuario, usado=False).update(usado=True)
            # Crear nuevo token
            token_obj = TokenRestablecimiento.objects.create(usuario=usuario)
            link = request.build_absolute_uri(f'/restablecer-password/{token_obj.token}/')

            # Enviar correo
            asunto = 'Restablecer contraseña — SenaFood'

            texto_plano = (
                f'Hola {usuario.nombre},\n\n'
                f'Recibimos una solicitud para restablecer tu contraseña.\n'
                f'Enlace válido por 30 minutos:\n{link}\n\n'
                f'Si no fuiste tú, ignora este mensaje.\n— Equipo SenaFood'
            )

            html = f"""
                <!DOCTYPE html>
                <html lang="es">
                <head><meta charset="UTF-8"></head>
                <body style="margin:0;padding:0;background:#f0f4f0;font-family:Arial,sans-serif;">
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f0;padding:40px 0;">
                    <tr><td align="center">
                    <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

                        <!-- HEADER -->
                        <tr>
                        <td style="background:#28a745;padding:30px;text-align:center;">
                            <h1 style="margin:0;color:#ffffff;font-size:24px;letter-spacing:2px;">🍽️ SENA FOOD</h1>
                            <p style="margin:6px 0 0;color:#c8f7d0;font-size:13px;">Sistema de Gestión de Restaurante</p>
                        </td>
                        </tr>

                        <!-- BODY -->
                        <tr>
                        <td style="padding:36px 40px;">
                            <h2 style="color:#1a1a1a;font-size:20px;margin:0 0 12px;">Restablece tu contraseña</h2>
                        <p style="color:#444;font-size:15px;line-height:1.6;margin:0 0 10px;">
                        Hola <strong>{usuario.nombre}</strong>,
                            </p>
                            <p style="color:#444;font-size:15px;line-height:1.6;margin:0 0 28px;">
                            Recibimos una solicitud para restablecer la contraseña de tu cuenta en SenaFood.
                            Haz clic en el botón para crear una nueva. Este enlace es válido por <strong>30 minutos</strong>.
                            </p>

                            <!-- BOTÓN -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                            <tr><td align="center" style="padding-bottom:28px;">
                                <a href="{link}"
                                style="background:#28a745;color:#ffffff;padding:14px 36px;border-radius:8px;
                                        text-decoration:none;font-size:15px;font-weight:bold;display:inline-block;
                                        letter-spacing:0.5px;">
                                Restablecer contraseña
                                </a>
                            </td></tr>
                            </table>

                            <!-- ENLACE ALTERNATIVO -->
                            <p style="color:#888;font-size:12px;line-height:1.6;margin:0 0 8px;">
                            Si el botón no funciona, copia y pega este enlace en tu navegador:
                            </p>
                            <p style="margin:0;">
                            <a href="{link}" style="color:#28a745;font-size:12px;word-break:break-all;">{link}</a>
                            </p>

                            <hr style="border:none;border-top:1px solid #e8e8e8;margin:28px 0;">

                            <p style="color:#aaa;font-size:12px;line-height:1.6;margin:0;text-align:center;">
                            Si no solicitaste este cambio, puedes ignorar este mensaje.<br>
                            Tu contraseña permanecerá sin cambios.
                            </p>
                        </td>
                        </tr>

                        <!-- FOOTER -->
                        <tr>
                        <td style="background:#f9fff9;padding:18px 40px;text-align:center;border-top:1px solid #e8f5e9;">
                        <p style="margin:0;color:#aaa;font-size:12px;">
                            © 2026 SenaFood · Todos los derechos reservados
                            </p>
                        </td>
                        </tr>

                    </table>
                    </td></tr>
                </table>
            </body>
            </html>
                """

            correo = EmailMultiAlternatives(
                subject=asunto,
                body=texto_plano,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            correo.attach_alternative(html, "text/html")
            correo.send(fail_silently=False)

            mensaje = "Te enviamos un enlace a tu correo. Revisa también la carpeta de spam."

        except Usuario.DoesNotExist:
            mensaje = "Te enviamos un enlace a tu correo. Revisa también la carpeta de spam."

    return render(request, 'gestion/solicitar_reset.html', {
        'mensaje': mensaje,
        'error': error,
    })


def restablecer_password_view(request, token):
    from django.contrib.auth.hashers import make_password
    error = None
    exito = None

    try:
        token_obj = TokenRestablecimiento.objects.get(token=token)
    except TokenRestablecimiento.DoesNotExist:
        return render(request, 'gestion/restablecer_password.html', {
            'error': 'El enlace no es válido.',
            'token_invalido': True,
        })

    if not token_obj.esta_vigente():
        return render(request, 'gestion/restablecer_password.html', {
            'error': 'El enlace expiró o ya fue usado. Solicita uno nuevo.',
            'token_invalido': True,
        })

    if request.method == 'POST':
        nueva = request.POST.get('nueva_password', '')
        confirmar = request.POST.get('confirmar_password', '')

        if len(nueva) < 8:
            error = 'La contraseña debe tener al menos 8 caracteres.'
        elif nueva != confirmar:
            error = 'Las contraseñas no coinciden.'
        else:
            token_obj.usuario.password = make_password(nueva)
            token_obj.usuario.save()
            token_obj.usado = True
            token_obj.save()
            exito = True

    return render(request, 'gestion/restablecer_password.html', {
        'error': error,
        'exito': exito,
        'token': token,
    })

def contacto_view(request):
    enviado = False
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip()
        asunto = request.POST.get('asunto', '').strip()
        mensaje = request.POST.get('mensaje', '').strip()

        if nombre and email and asunto and mensaje:
            try:
                html = f"""
                <!DOCTYPE html>
                <html lang="es">
                <head><meta charset="UTF-8"></head>
                <body style="margin:0;padding:0;background:#f0f4f0;font-family:Arial,sans-serif;">
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f0;padding:40px 0;">
                    <tr><td align="center">
                    <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                        <tr>
                        <td style="background:#28a745;padding:30px;text-align:center;">
                            <h1 style="margin:0;color:#ffffff;font-size:24px;letter-spacing:2px;">🍽️ SENA FOOD</h1>
                            <p style="margin:6px 0 0;color:#c8f7d0;font-size:13px;">Nuevo mensaje de contacto</p>
                        </td>
                        </tr>
                        <tr>
                        <td style="padding:36px 40px;">
                            <h2 style="color:#1a1a1a;font-size:18px;margin:0 0 20px;">📬 {asunto}</h2>
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
                            <tr>
                                <td style="padding:8px 0;border-bottom:1px solid #f0f0f0;">
                                <span style="color:#888;font-size:13px;">Nombre</span><br>
                                <strong style="color:#333;font-size:15px;">{nombre}</strong>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:8px 0;border-bottom:1px solid #f0f0f0;">
                                <span style="color:#888;font-size:13px;">Correo</span><br>
                                <strong style="color:#28a745;font-size:15px;">{email}</strong>
                                </td>
                            </tr>
                            </table>
                            <div style="background:#f9fff9;border-left:4px solid #28a745;padding:16px;border-radius:6px;">
                            <p style="color:#444;font-size:15px;line-height:1.7;margin:0;">{mensaje}</p>
                            </div>
                            <hr style="border:none;border-top:1px solid #e8e8e8;margin:28px 0;">
                            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
                            Este mensaje fue enviado desde el formulario de contacto de SenaFood.
                            </p>
                        </td>
                        </tr>
                        <tr>
                        <td style="background:#f9fff9;padding:18px 40px;text-align:center;border-top:1px solid #e8f5e9;">
                            <p style="margin:0;color:#aaa;font-size:12px;">© 2026 SenaFood · Todos los derechos reservados</p>
                        </td>
                        </tr>
                    </table>
                    </td></tr>
                    </table>
                </body>
                </html>
                """
                correo = EmailMultiAlternatives(
                    subject=f'Contacto SenaFood — {asunto}',
                    body=f'Nombre: {nombre}\nCorreo: {email}\n\nMensaje:\n{mensaje}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=['senafoodcdsf@gmail.com'],
                    reply_to=[email],
                )
                correo.attach_alternative(html, "text/html")
                correo.send(fail_silently=False)
                enviado = True
            except Exception as e:
                error = 'Hubo un problema al enviar el mensaje. Intenta de nuevo.'
        else:
            error = 'Por favor completa todos los campos.'

    return render(request, 'gestion/contacto.html', {
        'enviado': enviado,
        'error': error,
    })

def toggle_tienda_view(request):
    rol = request.session.get('usuario_rol', '')
    if rol not in ['Administrador', 'Cajero']:
        return redirect('dashboard')

    if request.method == 'POST':
        config = ConfiguracionTienda.get()
        config.tienda_abierta = not config.tienda_abierta
        usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])
        config.actualizado_por = usuario
        config.save()

    return redirect('catalogo')

def nosotros_view(request):
    return render(request, 'gestion/nosotros.html')
    

