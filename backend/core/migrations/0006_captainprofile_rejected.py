from django.db import migrations, models


class Migration(migrations.Migration):
    """Adds an explicit rejected flag so approval can be pending/approved/rejected.

    Schema-only: existing rows receive the default (False) and no existing
    value is read, rewritten or deleted.
    """
    dependencies = [("core", "0005_ride_coordinates")]
    operations = [
        migrations.AddField(model_name="captainprofile", name="rejected",
                            field=models.BooleanField(default=False)),
    ]
