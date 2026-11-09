from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0008_captain_documents_arrival")]
    operations = [
        migrations.AddField(
            model_name="order",
            name="dropoff_notes",
            field=models.TextField(blank=True),
        ),
    ]
