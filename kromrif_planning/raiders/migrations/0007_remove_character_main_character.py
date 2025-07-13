# Generated manually to remove main_character field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('raiders', '0006_remove_character_rank'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='character',
            name='main_character',
        ),
    ]