from django.db import models

class PQRSF(models.Model):

    TIPO_CHOICES = [
        ('Petición', 'Petición'),
        ('Queja', 'Queja'),
        ('Reclamo', 'Reclamo'),
        ('Sugerencia', 'Sugerencia'),
        ('Felicitación', 'Felicitación'),
    ]

    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Leída', 'Leída'),
        ('En gestión', 'En gestión'),
        ('Resuelta', 'Resuelta'),
        ('Cerrada', 'Cerrada'),
    ]

    id_pqrsf = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    # Cambia esta línea (línea 25 aprox):
    usuario = models.ForeignKey('gestion.Usuario', on_delete=models.CASCADE, db_column='id_usuario')
    respuesta = models.TextField(blank=True, null=True)
    leida = models.BooleanField(default=False)
    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True  # ya existe la tabla en MySQL
        db_table = 'pqrsf'
        verbose_name = 'PQRSF'
        verbose_name_plural = 'PQRSFs'

    def __str__(self):
        return f"{self.tipo} - {self.usuario} ({self.estado})"
