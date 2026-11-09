from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import *

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone", "identity_number", "role", "language", "profile_image", "is_active", "subscription_required", "must_change_password"]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name", "phone", "role", "language"]
    def validate_role(self, value):
        if value != "customer":
            raise serializers.ValidationError("Merchant, captain and admin accounts must be created or approved by an administrator.")
        return value
    def create(self, data):
        password = data.pop("password")
        return User.objects.create_user(password=password, **data)

class MerchantPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantProfile
        fields = ["id", "shop_name", "image", "cover_image", "description", "category", "address", "latitude", "longitude", "is_open", "rating"]

class MerchantProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantProfile
        fields = ["id", "shop_name", "image", "cover_image", "description", "category", "address", "latitude", "longitude", "opening_hours", "is_open", "rating"]
        read_only_fields = ["id", "is_open", "rating"]

    def validate_latitude(self, value):
        if value is not None and not Decimal("-90") <= value <= Decimal("90"):
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if value is not None and not Decimal("-180") <= value <= Decimal("180"):
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value

    def validate(self, attrs):
        latitude = attrs.get("latitude", getattr(self.instance, "latitude", None))
        longitude = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError("Provide both store coordinates.")
        return attrs

class ProductSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.shop_name", read_only=True)
    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ["merchant"]

class OrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    customer_profile_image = serializers.SerializerMethodField()
    captain_profile_image = serializers.SerializerMethodField()
    captain_latitude = serializers.SerializerMethodField()
    captain_longitude = serializers.SerializerMethodField()
    captain_location_updated_at = serializers.SerializerMethodField()
    merchant_name = serializers.CharField(source="merchant.shop_name", read_only=True)
    captain_name = serializers.CharField(source="captain.user.get_full_name", read_only=True)
    merchant = serializers.PrimaryKeyRelatedField(queryset=MerchantProfile.objects.all(), required=False, allow_null=True)
    items = serializers.ListField(child=serializers.DictField(), required=False)
    def get_customer_profile_image(self, obj):
        return self._profile_url(obj.customer)

    def get_captain_profile_image(self, obj):
        return self._profile_url(obj.captain.user) if obj.captain_id else None

    def get_captain_latitude(self, obj):
        return obj.captain.current_latitude if obj.captain_id and obj.status in ("assigned", "picked_up", "delivering") else None

    def get_captain_longitude(self, obj):
        return obj.captain.current_longitude if obj.captain_id and obj.status in ("assigned", "picked_up", "delivering") else None

    def get_captain_location_updated_at(self, obj):
        return obj.captain.current_location_updated_at if obj.captain_id and obj.status in ("assigned", "picked_up", "delivering") else None

    def _profile_url(self, user):
        if not user.profile_image:
            return None
        request = self.context.get("request")
        url = user.profile_image.url
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = ["customer", "captain", "status", "accepted_at", "ready_at", "created_at", "updated_at", "total", "subtotal", "request_key"]

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.method == "POST":
            if request.user.role != "customer":
                raise serializers.ValidationError("Only customers can create orders.")
            order_type = attrs.get("order_type", "store")
            if order_type == "ride":
                raise serializers.ValidationError("Use the dedicated /orders/ride/ endpoint to create a ride request.")
            if order_type != "store":
                raise serializers.ValidationError("Parcel requests are not enabled in this release.")
            if order_type == "store":
                merchant = attrs.get("merchant")
                if not merchant or not merchant.is_open:
                    raise serializers.ValidationError({"merchant": "Choose an open merchant."})
                raw_items = attrs.get("items", [])
                if not raw_items:
                    raise serializers.ValidationError({"items": "Add at least one product."})
                normalized, subtotal = [], 0
                for row in raw_items:
                    try:
                        product_id, quantity = int(row.get("product_id")), int(row.get("quantity", 1))
                    except (TypeError, ValueError):
                        raise serializers.ValidationError({"items": "Each item needs product_id and quantity."})
                    if quantity < 1 or quantity > 50:
                        raise serializers.ValidationError({"items": "Quantity must be between 1 and 50."})
                    try:
                        product = Product.objects.get(pk=product_id, merchant=merchant, available=True)
                    except Product.DoesNotExist:
                        raise serializers.ValidationError({"items": f"Product {product_id} is unavailable."})
                    line = product.price * quantity
                    subtotal += line
                    normalized.append({"product_id": product.id, "name": product.name, "quantity": quantity, "unit_price": str(product.price), "line_total": str(line)})
                attrs["items"] = normalized
                attrs["subtotal"] = subtotal
                # Persist the merchant pickup point on every store order so admin,
                # merchant and authorized delivery views share the same origin.
                attrs["pickup_address"] = merchant.address or merchant.shop_name
                attrs["pickup_latitude"] = merchant.latitude
                attrs["pickup_longitude"] = merchant.longitude
                dlat = attrs.get("dropoff_latitude")
                dlon = attrs.get("dropoff_longitude")
                if (dlat is None) != (dlon is None):
                    raise serializers.ValidationError({"location": "Provide both delivery coordinates."})
                if dlat is not None and not (-90 <= float(dlat) <= 90 and -180 <= float(dlon) <= 180):
                    raise serializers.ValidationError({"location": "Delivery coordinates are outside valid ranges."})
                # Fees remain zero until the commercial pricing rules are approved.
                attrs["delivery_fee"] = Decimal("0.00")
                attrs["checkpoint_fee"] = Decimal("0.00")
                attrs["total"] = subtotal
        return attrs

class SettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashSettlement
        fields = "__all__"
        read_only_fields = ["reference", "closed", "closed_at"]

class DelayReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DelayReport
        fields = "__all__"
        read_only_fields = ["captain", "reviewed", "reported_at"]

class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = "__all__"
        read_only_fields = ["user", "status", "created_at"]
