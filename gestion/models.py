from django.db import models

from django.db import models
from pqrs.models import PQRSF
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255, blank=True, null=True)
    apellido = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(unique=True, max_length=255)
    password = models.CharField(db_column='contraseña', max_length=255)   
    telefono = models.CharField(max_length=255, blank=True, null=True)
    tipo_identificacion = models.CharField(db_column='tipo_identificacion', max_length=255, blank=True, null=True)
    numero_identificacion = models.CharField(db_column='numero_identificacion', max_length=255, blank=True, null=True)
    rol = models.ForeignKey('Rol', on_delete=models.CASCADE, db_column='id_rol')
    es_activo = models.BooleanField(default=True, db_column='es_activo')

    # Auditoría automática
    create_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    update_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'usuario'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.email})"

class Calificacion(models.Model):
    id_calificacion = models.AutoField(primary_key=True)
    puntuacion = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comentario = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, db_column='id_usuario')
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE, db_column='id_producto')
    carrito = models.ForeignKey('Carrito', on_delete=models.CASCADE, db_column='id_carrito')

    class Meta:
        managed = True
        db_table = 'calificacion'
        verbose_name = 'Calificación'
        verbose_name_plural = 'Calificaciones'

    def __str__(self):
        return f"Calificación {self.puntuacion} - {self.usuario.nombre}"

class Carrito(models.Model):

    ESTADOS = [
        ('abierto',           'Abierto'),
        ('pendiente_pago',    'Pendiente de pago'),
        ('pagado',            'Pagado'),
        ('pendiente_entrega', 'Pendiente de entrega'),
        ('entregado',         'Entregado'),
    ]

    id_carrito          = models.AutoField(primary_key=True)
    usuario             = models.ForeignKey('Usuario', on_delete=models.CASCADE, db_column='id_usuario')
    total               = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    estado              = models.CharField(max_length=50, blank=True, null=True, choices=ESTADOS)
    fecha               = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    metodopago          = models.CharField(db_column='metodoPago', max_length=50, blank=True, null=True)
    numerofactura       = models.CharField(db_column='numeroFactura', max_length=50, blank=True, null=True)
    fecha_confirmacion  = models.DateTimeField(blank=True, null=True)
    fecha_entrega       = models.DateTimeField(blank=True, null=True)
    create_at           = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    update_at           = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        managed  = True
        db_table = 'carrito'

    def __str__(self):
        return f'Pedido #{self.id_carrito} - {self.usuario.nombre} - {self.estado}'


class DetallePedido(models.Model):
    id_detalle_pedido = models.BigAutoField(primary_key=True)
    cantidad = models.IntegerField()
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE, db_column='id_producto')    
    # Estos campos son útiles para mantener un registro histórico del precio al momento de la compra
    nombre_producto = models.CharField(max_length=255, blank=True, null=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    pedido = models.ForeignKey('Pedido', on_delete=models.CASCADE, db_column='id_pedido')

    class Meta:
        managed = True
        db_table = 'detalle_pedido'
        verbose_name = 'Detalle del Pedido'
        verbose_name_plural = 'Detalles de los Pedidos'

    def __str__(self):
        # Usamos self.pedido.id_pedido para que el nombre sea descriptivo en el admin
        return f"Detalle {self.id_detalle_pedido} - Producto: {self.nombre_producto} (Pedido {self.pedido.id_pedido})"


class Detallecarrito(models.Model):
    id_detalle      = models.AutoField(primary_key=True)
    id_carrito      = models.ForeignKey(Carrito, models.DO_NOTHING, db_column='id_carrito')
    id_producto     = models.ForeignKey('Producto', models.DO_NOTHING, db_column='id_producto')
    cantidad        = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        managed  = True
        db_table = 'detallecarrito'

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario



class Fidelizacion(models.Model):
    idfidelizacion = models.AutoField(db_column='idFidelizacion', primary_key=True)  # Field name made lowercase.
    puntos = models.IntegerField(blank=True, null=True)
    nivel = models.CharField(max_length=30, blank=True, null=True)
    idusuario = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='idUsuario')  # Field name made lowercase.

    class Meta:
        managed = True
        db_table = 'fidelizacion'


class HistorialUsuario(models.Model):
    id_historial = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_usuario', blank=True, null=True)
    campomodificado = models.CharField(db_column='campoModificado', max_length=50, blank=True, null=True)  # Field name made lowercase.
    valoranterior = models.TextField(db_column='valorAnterior', blank=True, null=True)  # Field name made lowercase.
    valornuevo = models.TextField(db_column='valorNuevo', blank=True, null=True)  # Field name made lowercase.
    fechacambio = models.DateTimeField(db_column='fechaCambio')  # Field name made lowercase.

    class Meta:
        managed = True
        db_table = 'historial_usuario'


class Inventario(models.Model):
    id_inventario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255, blank=True, null=True)
    idproducto = models.IntegerField(blank=True, null=True)
    ubicacion = models.CharField(max_length=255, blank=True, null=True)
    stocktotal = models.IntegerField(db_column='stockTotal', blank=True, null=True)  # Field name made lowercase.
    costouni = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    capacidad_maxima = models.IntegerField()
    alerta_minimos = models.IntegerField()
    responsable = models.CharField(max_length=255, blank=True, null=True)
    ultima_revision = models.DateField(blank=True, null=True)
    observaciones = models.CharField(max_length=500, blank=True, null=True)
    usuario_ultima_actualizacion = models.BigIntegerField(blank=True, null=True)
    create_at = models.DateTimeField(blank=True, null=True)
    update_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'inventario'


class MovimientosInventario(models.Model):
    id_movimiento = models.AutoField(primary_key=True)
    id_producto = models.ForeignKey('Producto', models.DO_NOTHING, db_column='id_producto')
    id_inventario = models.ForeignKey(Inventario, models.DO_NOTHING, db_column='id_inventario')
    tipo_movimiento = models.CharField(max_length=7)
    cantidad = models.IntegerField()
    fecha_movimiento = models.DateTimeField(blank=True, null=True)
    id_usuario = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_usuario')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'movimientos_inventario'

class Pedido(models.Model):
    id_pedido = models.BigAutoField(primary_key=True)
    # auto_now_add=True para que se registre la fecha en el momento exacto del pedido
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=255, blank=True, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # CORREGIDO: Ahora vinculado directamente con el Usuario
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, db_column='id_usuario')
    
    # Campos de auditoría automáticos
    create_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    update_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'pedido'
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

    def __str__(self):
        return f"Pedido #{self.id_pedido} - Cliente: {self.usuario.nombre} - Total: ${self.total}"


class Permiso(models.Model):
    id_permiso = models.AutoField(primary_key=True)
    nombrepermiso = models.CharField(db_column='nombrePermiso', max_length=50)  # Field name made lowercase.

    class Meta:
        managed = True
        db_table = 'permiso'


class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=500, blank=True, null=True)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(blank=True, null=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    categoria = models.CharField(max_length=255, blank=True, null=True)
    codigo_barras = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=255)
    create_at = models.DateTimeField(blank=True, null=True)
    update_at = models.DateTimeField(blank=True, null=True)
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    es_activo = models.BooleanField(default=True)
    motivo_desactivacion = models.CharField(max_length=20, blank=True, null=True)
    precio_promocion = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fecha_inicio_promo = models.DateField(blank=True, null=True)
    fecha_fin_promo = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'producto'

    @property
    def stock_actual(self):
        return self.stock or 0

    @property
    def stock_bajo(self):
        try:
            from inventario.models import Inventario
            inv = Inventario.objects.get(idproducto=self.id_producto)
            alerta_min = inv.alerta_minimos or 10
        except Exception:
            alerta_min = 10
        return self.stock is not None and self.stock <= alerta_min

    @property
    def en_promocion(self):
        from datetime import date
        hoy = date.today()
        return (
            self.precio_promocion is not None and
            self.fecha_inicio_promo is not None and
            self.fecha_fin_promo is not None and
            self.fecha_inicio_promo <= hoy <= self.fecha_fin_promo
        )

    def __str__(self):
        return self.nombre


class Promocion(models.Model):
    id_promocion = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    descuento = models.DecimalField(max_digits=38, decimal_places=2, blank=True, null=True)
    id_producto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='id_producto')
    update_at = models.DateTimeField(blank=True, null=True)
    create_at = models.DateTimeField(blank=True, null=True)
    fecha_incio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    fecha_inicio = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=255)

    class Meta:
        managed = True
        db_table = 'promocion'


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=255, blank=True, null=True)
    nombrerol = models.CharField(db_column='nombreRol', max_length=255, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = True
        db_table = 'rol'


class RolPermiso(models.Model):
    id_rol_permisorol = models.IntegerField(primary_key=True)
    id_rol = models.ForeignKey(Rol, models.DO_NOTHING, db_column='id_Rol')  # Field name made lowercase.
    idpermiso = models.ForeignKey(Permiso, models.DO_NOTHING, db_column='idPermiso')  # Field name made lowercase.

    class Meta:
        managed = True
        db_table = 'rol_permiso'

class TokenRestablecimiento(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    class Meta:
        db_table = 'token_restablecimiento'
        verbose_name = 'Token de Restablecimiento'

    def esta_vigente(self):
        from django.utils import timezone
        import datetime
        # El token dura 30 minutos
        ahora = datetime.datetime.now()
        diferencia = ahora - self.creado_en
        return not self.usado and diferencia.total_seconds() < 1800

class ConfiguracionTienda(models.Model):
    tienda_abierta = models.BooleanField(default=True)
    actualizado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    update_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'configuracion_tienda'
        verbose_name = 'Configuración de Tienda'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'tienda_abierta': True})
        return obj
