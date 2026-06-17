from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('producto', '0002_alter_proveedorproducto_options'),
        ('proveedor', '0001_initial'),
        ('gestion', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS `proveedor_producto` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `id_proveedor` INT NOT NULL,
                    `id_producto` INT NOT NULL,
                    `precio_proveedor` DECIMAL(10,2) DEFAULT NULL,
                    `es_activo` TINYINT(1) DEFAULT 1,
                    `create_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    KEY `id_proveedor` (`id_proveedor`),
                    KEY `id_producto` (`id_producto`),
                    CONSTRAINT `proveedor_producto_ibfk_1`
                        FOREIGN KEY (`id_proveedor`) REFERENCES `proveedor` (`id_proveedor`),
                    CONSTRAINT `proveedor_producto_ibfk_2`
                        FOREIGN KEY (`id_producto`) REFERENCES `producto` (`id_producto`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
            """,
            reverse_sql="DROP TABLE IF EXISTS `proveedor_producto`;",
        ),
    ]