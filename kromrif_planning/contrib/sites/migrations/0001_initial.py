"""
Sites migration.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Site",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("domain", models.CharField(max_length=100, verbose_name="domain name")),
                ("name", models.CharField(max_length=50, verbose_name="display name")),
            ],
            options={
                "verbose_name": "site",
                "verbose_name_plural": "sites",
                "db_table": "django_site",
            },
        ),
    ]