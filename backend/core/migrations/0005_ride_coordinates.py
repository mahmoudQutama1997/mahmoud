from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0004_user_profile_image")]
    operations = [
        migrations.AddField(model_name="order", name="pickup_latitude", field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name="order", name="pickup_longitude", field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name="order", name="dropoff_latitude", field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name="order", name="dropoff_longitude", field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name="order", name="distance_km", field=models.DecimalField(decimal_places=2, default=0, max_digits=8)),
    ]
