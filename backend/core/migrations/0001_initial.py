# Initial schema matching the original Waselni MVP before central accounts/subscriptions.
import django.contrib.auth.models
import django.contrib.auth.validators
import django.utils.timezone
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("username", models.CharField(error_messages={"unique": "A user with that username already exists."}, help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.", max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name="username")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email address")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("role", models.CharField(choices=[("customer", "Customer"), ("merchant", "Merchant"), ("captain", "Captain"), ("admin", "Admin")], default="customer", max_length=20)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("language", models.CharField(choices=[("ar", "العربية"), ("he", "עברית"), ("en", "English")], default="ar", max_length=2)),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={"verbose_name": "user", "verbose_name_plural": "users", "abstract": False},
            managers=[("objects", django.contrib.auth.models.UserManager())],
        ),
        migrations.CreateModel(
            name="MerchantProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shop_name", models.CharField(max_length=160)), ("category", models.CharField(default="supermarket", max_length=40)),
                ("address", models.CharField(blank=True, max_length=255)), ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)), ("opening_hours", models.CharField(blank=True, max_length=120)),
                ("is_open", models.BooleanField(default=True)), ("rating", models.DecimalField(decimal_places=2, default=5, max_digits=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="merchant_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="CaptainProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vehicle_type", models.CharField(choices=[("car", "Car"), ("motorcycle", "Motorcycle"), ("truck", "Truck")], default="motorcycle", max_length=20)),
                ("vehicle_model", models.CharField(blank=True, max_length=100)), ("plate_number", models.CharField(blank=True, max_length=30)),
                ("permit_type", models.CharField(choices=[("jerusalem_id", "Jerusalem ID"), ("west_bank", "West Bank"), ("work_permit", "Work Permit")], default="west_bank", max_length=30)),
                ("checkpoint_badge", models.BooleanField(default=False)), ("license_verified", models.BooleanField(default=False)),
                ("insurance_verified", models.BooleanField(default=False)), ("approved", models.BooleanField(default=False)),
                ("online", models.BooleanField(default=False)), ("rating", models.DecimalField(decimal_places=2, default=5, max_digits=3)),
                ("current_latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("current_longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="captain_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)), ("category", models.CharField(blank=True, max_length=80)),
                ("description", models.TextField(blank=True)), ("image", models.ImageField(blank=True, null=True, upload_to="products/")),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)), ("available", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="products", to="core.merchantprofile")),
            ],
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_type", models.CharField(choices=[("ride", "Ride"), ("parcel", "Parcel"), ("store", "Store")], default="store", max_length=20)),
                ("required_vehicle", models.CharField(choices=[("any", "Any vehicle"), ("car", "Car"), ("motorcycle", "Motorcycle"), ("truck", "Truck")], default="any", max_length=20)),
                ("status", models.CharField(choices=[("new", "New"), ("accepted", "Accepted"), ("preparing", "Preparing"), ("ready", "Ready"), ("assigned", "Assigned"), ("picked_up", "Picked_up"), ("delivering", "Delivering"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="new", max_length=20)),
                ("items", models.JSONField(blank=True, default=list)), ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("delivery_fee", models.DecimalField(decimal_places=2, default=0, max_digits=10)), ("checkpoint_fee", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=10)), ("payment_method", models.CharField(choices=[("cash", "Cash"), ("online", "Online")], default="cash", max_length=10)),
                ("pickup_address", models.CharField(blank=True, max_length=255)), ("dropoff_address", models.CharField(blank=True, max_length=255)),
                ("requires_checkpoint", models.BooleanField(default=False)), ("prep_minutes", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)), ("ready_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("captain", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="core.captainprofile")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customer_orders", to=settings.AUTH_USER_MODEL)),
                ("merchant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="core.merchantprofile")),
            ],
        ),
        migrations.CreateModel(
            name="CashSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("confirmed_by_merchant", models.BooleanField(default=False)), ("confirmed_by_captain", models.BooleanField(default=False)), ("closed", models.BooleanField(default=False)),
                ("reference", models.CharField(max_length=32, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("captain", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.captainprofile")),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.merchantprofile")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="settlement", to="core.order")),
            ],
        ),
        migrations.CreateModel(
            name="DelayReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("arrived_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("reported_at", models.DateTimeField(auto_now_add=True)), ("wait_minutes", models.PositiveSmallIntegerField(default=10)), ("details", models.TextField(blank=True)),
                ("reviewed", models.BooleanField(default=False)), ("captain", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.captainprofile")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delay_reports", to="core.order")),
            ],
        ),
        migrations.CreateModel(
            name="Rating",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("target_type", models.CharField(max_length=20)),
                ("score", models.PositiveSmallIntegerField()), ("comment", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ratings", to="core.order")),
            ],
        ),
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("subject", models.CharField(max_length=180)),
                ("message", models.TextField()), ("status", models.CharField(choices=[("open", "Open"), ("in_review", "In review"), ("resolved", "Resolved")], default="open", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.order")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
