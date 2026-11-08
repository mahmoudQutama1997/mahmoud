from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0007_order_idempotency_key")]
    operations = [
        migrations.AddField(
            model_name="captainprofile", name="identity_document",
            field=models.FileField(blank=True, null=True, upload_to="captain_documents/identity/"),
        ),
        migrations.AddField(
            model_name="captainprofile", name="driving_license_document",
            field=models.FileField(blank=True, null=True, upload_to="captain_documents/licenses/"),
        ),
        migrations.AddField(
            model_name="captainprofile", name="insurance_document",
            field=models.FileField(blank=True, null=True, upload_to="captain_documents/insurance/"),
        ),
        migrations.AddField(
            model_name="captainprofile", name="digital_undertaking_signed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order", name="merchant_arrived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
