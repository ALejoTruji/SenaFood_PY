from django.db import models
from proveedor.models import Proveedor
from gestion.models import Producto, Usuario


class ProveedorProducto(models.Model):
    id = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, db_column='id_proveedor')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='id_producto')
    precio_proveedor = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    es_activo = models.BooleanField(default=True)
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'proveedor_producto'
        verbose_name = 'Proveedor-Producto'
        unique_together = ('proveedor', 'producto')

    def __str__(self):
        return f"{self.proveedor.nombre} → {self.producto.nombre}"