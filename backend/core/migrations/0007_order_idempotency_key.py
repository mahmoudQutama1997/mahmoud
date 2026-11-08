from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_captainprofile_rejected")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="request_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                fields=("customer", "request_key"),
                name="uniq_order_customer_request_key",
            ),
        ),
    ]
