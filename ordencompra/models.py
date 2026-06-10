from django.db import models


class OrdenCompra(models.Model):

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('enviada',   'Enviada'),
        ('recibida',  'Recibida'),
        ('cerrada',   'Cerrada'),
    ]

    id_orden        = models.BigAutoField(primary_key=True)
    fecha           = models.DateField(auto_now_add=True)
    estado          = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    observaciones   = models.TextField(blank=True, null=True)
    total           = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    create_at       = models.DateTimeField(auto_now_add=True)
    update_at       = models.DateTimeField(auto_now=True)

    id_proveedor    = models.ForeignKey(
        'proveedor.Proveedor', on_delete=models.PROTECT, db_column='id_proveedor'
    )
    id_usuario      = models.ForeignKey(
        'gestion.Usuario', on_delete=models.SET_NULL, null=True, db_column='id_usuario'
    )

    class Meta:
        managed  = True
        db_table = 'orden_compra'
        verbose_name = 'Orden de Compra'
        verbose_name_plural = 'Órdenes de Compra'
        ordering = ['-create_at']

    def __str__(self):
        return f'Orden #{self.id_orden} — {self.id_proveedor} — {self.estado}'


class DetalleOrdenCompra(models.Model):
    id_detalle      = models.BigAutoField(primary_key=True)
    orden           = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE,
                                        related_name='detalles', db_column='id_orden')
    producto        = models.ForeignKey('gestion.Producto', on_delete=models.PROTECT,
                                        db_column='id_producto')
    nombre_producto = models.CharField(max_length=255)
    cantidad        = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal        = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed  = True
        db_table = 'detalle_orden_compra'
        verbose_name = 'Detalle de Orden de Compra'

    def __str__(self):
        return f'Detalle #{self.id_detalle} — {self.nombre_producto}'