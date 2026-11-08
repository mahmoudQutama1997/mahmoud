from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [(x, x.title()) for x in ["customer","merchant","captain","admin"]]
    LANGUAGE_CHOICES = [("ar","العربية"),("he","עברית"),("en","English")]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="customer")
    phone = models.CharField(max_length=30, blank=True)
    identity_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    subscription_required = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ar")
    profile_image = models.ImageField(upload_to="profiles/", blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = "admin"
        super().save(*args, **kwargs)

class MerchantProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="merchant_profile")
    shop_name = models.CharField(max_length=160)
    image = models.ImageField(upload_to="stores/logos/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="stores/covers/", blank=True, null=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=40, default="supermarket")
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    opening_hours = models.CharField(max_length=120, blank=True)
    is_open = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.shop_name

class CaptainProfile(models.Model):
    VEHICLES = [("car","Car"),("motorcycle","Motorcycle"),("truck","Truck")]
    PERMITS = [("jerusalem_id","Jerusalem ID"),("west_bank","West Bank"),("work_permit","Work Permit")]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="captain_profile")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLES, default="motorcycle")
    vehicle_model = models.CharField(max_length=100, blank=True)
    plate_number = models.CharField(max_length=30, blank=True)
    permit_type = models.CharField(max_length=30, choices=PERMITS, default="west_bank")
    checkpoint_badge = models.BooleanField(default=False)
    license_verified = models.BooleanField(default=False)
    insurance_verified = models.BooleanField(default=False)
    identity_document = models.FileField(upload_to="captain_documents/identity/", blank=True, null=True)
    driving_license_document = models.FileField(upload_to="captain_documents/licenses/", blank=True, null=True)
    insurance_document = models.FileField(upload_to="captain_documents/insurance/", blank=True, null=True)
    digital_undertaking_signed_at = models.DateTimeField(null=True, blank=True)
    approved = models.BooleanField(default=False)
    rejected = models.BooleanField(default=False)
    online = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5)
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

class Product(models.Model):
    merchant = models.ForeignKey(MerchantProfile, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class Order(models.Model):
    TYPES = [("ride","Ride"),("parcel","Parcel"),("store","Store")]
    STATUSES = [(x,x.title()) for x in ["new","accepted","preparing","ready","assigned","picked_up","delivering","completed","cancelled"]]
    PAYMENT = [("cash","Cash"),("online","Online")]
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer_orders")
    merchant = models.ForeignKey(MerchantProfile, on_delete=models.PROTECT, null=True, blank=True, related_name="orders")
    captain = models.ForeignKey(CaptainProfile, on_delete=models.PROTECT, null=True, blank=True, related_name="orders")
    order_type = models.CharField(max_length=20, choices=TYPES, default="store")
    REQUIRED_VEHICLES = [("any", "Any vehicle"), ("car", "Car"), ("motorcycle", "Motorcycle"), ("truck", "Truck")]
    required_vehicle = models.CharField(max_length=20, choices=REQUIRED_VEHICLES, default="any")
    status = models.CharField(max_length=20, choices=STATUSES, default="new")
    items = models.JSONField(default=list, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checkpoint_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=PAYMENT, default="cash")
    pickup_address = models.CharField(max_length=255, blank=True)
    dropoff_address = models.CharField(max_length=255, blank=True)
    dropoff_notes = models.TextField(blank=True)
    requires_checkpoint = models.BooleanField(default=False)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    dropoff_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    dropoff_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    prep_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    merchant_arrived_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    request_key = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["customer", "request_key"], name="uniq_order_customer_request_key"),
        ]

class CashSettlement(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="settlement")
    merchant = models.ForeignKey(MerchantProfile, on_delete=models.PROTECT)
    captain = models.ForeignKey(CaptainProfile, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    confirmed_by_merchant = models.BooleanField(default=False)
    confirmed_by_captain = models.BooleanField(default=False)
    closed = models.BooleanField(default=False)
    reference = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

class DelayReport(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="delay_reports")
    captain = models.ForeignKey(CaptainProfile, on_delete=models.PROTECT)
    arrived_at = models.DateTimeField(default=timezone.now)
    reported_at = models.DateTimeField(auto_now_add=True)
    wait_minutes = models.PositiveSmallIntegerField(default=10)
    details = models.TextField(blank=True)
    reviewed = models.BooleanField(default=False)

class Rating(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="ratings")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    target_type = models.CharField(max_length=20)
    score = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SupportTicket(models.Model):
    STATUSES = [("open","Open"),("in_review","In review"),("resolved","Resolved")]
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    subject = models.CharField(max_length=180)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUSES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)


class Subscription(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("pending", "Pending payment"), ("expired", "Expired"), ("cancelled", "Cancelled")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    months = models.PositiveSmallIntegerField(default=1)
    currency = models.CharField(max_length=8, default="ILS")
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_on", "-created_at"]

    def __str__(self):
        return f"{self.user.username} · {self.amount} {self.currency} · {self.starts_on}"

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.status == "active" and self.starts_on <= today <= self.ends_on


class SubscriptionPayment(models.Model):
    METHODS = [("cash", "Cash"), ("bank", "Bank transfer"), ("online", "Online"), ("other", "Other")]
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=12, choices=METHODS, default="cash")
    reference = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-paid_at"]
