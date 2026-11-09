from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def promote_superusers_to_admin(apps, schema_editor):
    User = apps.get_model("core", "User")
    User.objects.filter(is_superuser=True).update(role="admin")


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="user", name="identity_number",
            field=models.CharField(blank=True, max_length=40, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="user", name="subscription_required",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user", name="must_change_password",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(promote_superusers_to_admin, migrations.RunPython.noop),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)), ("months", models.PositiveSmallIntegerField(default=1)),
                ("currency", models.CharField(default="ILS", max_length=8)),
                ("starts_on", models.DateField()), ("ends_on", models.DateField()),
                ("status", models.CharField(choices=[("active", "Active"), ("pending", "Pending payment"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="active", max_length=16)),
                ("notes", models.CharField(blank=True, max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_subscriptions", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-starts_on", "-created_at"]},
        ),
        migrations.CreateModel(
            name="SubscriptionPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("method", models.CharField(choices=[("cash", "Cash"), ("bank", "Bank transfer"), ("online", "Online"), ("other", "Other")], default="cash", max_length=12)),
                ("reference", models.CharField(blank=True, max_length=100)), ("notes", models.CharField(blank=True, max_length=500)),
                ("paid_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="core.subscription")),
            ],
            options={"ordering": ["-paid_at"]},
        ),
    ]
