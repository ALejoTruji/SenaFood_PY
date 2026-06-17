from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pqrs', '0002_alter_pqrsf_options'),
        ('gestion', '0002_alter_usuario_password'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS `pqrsf` (
                            `id_pqrsf` INT AUTO_INCREMENT PRIMARY KEY,
                            `tipo` VARCHAR(50) NOT NULL,
                            `descripcion` LONGTEXT NOT NULL,
                            `estado` VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
                            `respuesta` LONGTEXT NULL,
                            `leida` BOOLEAN NOT NULL DEFAULT 0,
                            `create_at` DATETIME(6) NOT NULL,
                            `update_at` DATETIME(6) NOT NULL,
                            `id_usuario` INT NOT NULL,
                            CONSTRAINT `pqrsf_id_usuario_fk`
                                FOREIGN KEY (`id_usuario`) REFERENCES `usuario` (`id_usuario`)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                    """,
                    reverse_sql="DROP TABLE IF EXISTS `pqrsf`;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='pqrsf',
                    name='usuario',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='gestion.usuario',
                        db_column='id_usuario',
                    ),
                ),
            ],
        ),
    ]