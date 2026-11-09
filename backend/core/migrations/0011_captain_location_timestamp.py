from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0010_alter_order_status")]

    operations = [
        migrations.AddField(
            model_name="captainprofile",
            name="current_location_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
