from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0002_central_accounts_subscriptions")]

    operations = [
        migrations.AddField(
            model_name="merchantprofile",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="stores/logos/"),
        ),
        migrations.AddField(
            model_name="merchantprofile",
            name="cover_image",
            field=models.ImageField(blank=True, null=True, upload_to="stores/covers/"),
        ),
        migrations.AddField(
            model_name="merchantprofile",
            name="description",
            field=models.TextField(blank=True),
        ),
    ]
