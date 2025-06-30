"""
Alter site domain unique constraint.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="site",
            name="domain",
            field=models.CharField(
                max_length=100, unique=True, verbose_name="domain name"
            ),
        ),
    ]