from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0003_merchantprofile_images_description")]
    operations = [migrations.AddField(
        model_name="user",
        name="profile_image",
        field=models.ImageField(blank=True, null=True, upload_to="profiles/"),
    )]
