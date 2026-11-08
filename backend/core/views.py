import uuid
import os
import secrets
import calendar
import math
from datetime import date, timedelta
from decimal import Decimal
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import generics, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import *
from .serializers import *
from .services.eligibility import (
    subscription_state, classify_subscription, evaluate_captain, legacy_fields, enforce_online_invariant,
    eligible_captain_user_ids, order_compatibility_reasons, set_approval, APPROVAL_STATUSES,
)


def as_bool(value):
    """JSON booleans pass through; form strings such as "false" are not truthy."""
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def publish_order_event(order, event="order.updated"):
    """Send a small event; clients fetch authorized order data through REST."""
    layer = get_channel_layer()
    if not layer:
        return
    payload = {"type": event, "order_id": order.id, "status": order.status, "updated_at": order.updated_at.isoformat()}
    groups = {"role_admin"}
    if order.customer_id:
        groups.add(f"user_{order.customer_id}")
    if order.merchant_id and order.merchant:
        groups.add(f"user_{order.merchant.user_id}")
    if order.captain_id and order.captain:
        groups.add(f"user_{order.captain.user_id}")
    # Captains are targeted individually, and only if the shared eligibility
    # service says they may receive this order right now.
    dispatchable = not order.captain_id and (
        (order.order_type == "ride" and order.status == "new") or
        (order.order_type != "ride" and order.status == "ready"))
    if dispatchable:
        captain_ids = eligible_captain_user_ids(order)
    elif order.status in ("assigned", "cancelled"):
        captain_ids = eligible_captain_user_ids()  # refresh stale available-order lists
    else:
        captain_ids = []
    groups.update(f"user_{uid}" for uid in captain_ids)
    for group in groups:
        async_to_sync(layer.group_send)(group, {"type": "order_event", "payload": payload})


def publish_captain_eligibility(user):
    """Push the fresh eligibility snapshot to one captain's open sockets."""
    layer = get_channel_layer()
    if not layer or user.role != "captain":
        return
    try:
        profile = user.captain_profile
    except CaptainProfile.DoesNotExist:
        return
    elig = enforce_online_invariant(profile)
    async_to_sync(layer.group_send)(f"user_{user.id}", {"type": "order_event",
        "payload": {"type": "captain.eligibility", "eligibility": elig}})


class RegisterView(APIView):
    """Public self-registration is restricted to customer accounts.

    Merchant, captain and administrator identities are provisioned by the
    authenticated platform administration workflow.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        role = str(data.get("role", "customer")).strip().lower()
        if role != "customer":
            raise ValidationError({"role": "Public registration is for customers only. Merchant and captain accounts must be created by an administrator."})
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        first_name = str(data.get("first_name", "")).strip()
        last_name = str(data.get("last_name", "")).strip()
        phone = str(data.get("phone", "")).strip()
        if not username or not first_name or not phone or len(password) < 8:
            raise ValidationError({"detail": "Username, first name, phone and a password of at least 8 characters are required."})
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError({"username": "This username is already in use."})
        if role == "merchant" and not str(data.get("shop_name", "")).strip():
            raise ValidationError({"shop_name": "Store name is required."})
        if role == "captain":
            if data.get("vehicle_type", "motorcycle") not in dict(CaptainProfile.VEHICLES):
                raise ValidationError({"vehicle_type": "Choose a valid vehicle type."})
            if data.get("permit_type", "west_bank") not in dict(CaptainProfile.PERMITS):
                raise ValidationError({"permit_type": "Choose a valid permit type."})
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(password)
        except Exception as exc:
            raise ValidationError({"password": list(getattr(exc, "messages", [str(exc)]))})
        for field in ("profile_image", "store_image", "cover_image", "identity_document", "driving_license_document", "insurance_document"):
            uploaded = request.FILES.get(field)
            if uploaded and (uploaded.size > (5 if field in ("profile_image", "store_image", "cover_image") else 10) * 1024 * 1024 or (field in ("profile_image", "store_image", "cover_image") and uploaded.content_type not in ("image/jpeg", "image/png", "image/webp")) or (field not in ("profile_image", "store_image", "cover_image") and not uploaded.name.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")))):
                raise ValidationError({field: "Upload a JPG, PNG or WEBP image up to 5 MB."})
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, password=password, email=str(data.get("email", "")).strip(),
                first_name=first_name, last_name=last_name, phone=phone, role=role,
                language=data.get("language", "ar") if data.get("language", "ar") in ("ar", "en", "he") else "ar",
                subscription_required=role in ("merchant", "captain"),
            )
            if request.FILES.get("profile_image"):
                user.profile_image = request.FILES["profile_image"]
                user.save(update_fields=["profile_image"])
            if role == "merchant":
                MerchantProfile.objects.create(
                    user=user, shop_name=str(data.get("shop_name", "")).strip(),
                    category=str(data.get("category", "general")).strip()[:40] or "general",
                    description=str(data.get("description", "")).strip(),
                    address=str(data.get("address", "")).strip(),
                    image=request.FILES.get("store_image"), cover_image=request.FILES.get("cover_image"),
                    is_open=False,
                )
            elif role == "captain":
                undertaking = as_bool(data.get("digital_undertaking"))
                if not undertaking:
                    raise ValidationError({"digital_undertaking": "You must accept the digital undertaking."})
                CaptainProfile.objects.create(
                    user=user, identity_document=request.FILES.get("identity_document"),
                    driving_license_document=request.FILES.get("driving_license_document"),
                    insurance_document=request.FILES.get("insurance_document"),
                    digital_undertaking_signed_at=timezone.now(),
                    vehicle_type=data.get("vehicle_type", "motorcycle"),
                    vehicle_model=str(data.get("vehicle_model", "")).strip()[:100],
                    plate_number=str(data.get("plate_number", "")).strip()[:30],
                    permit_type=data.get("permit_type", "west_bank"),
                    approved=False, rejected=False, online=False,
                )
        return Response({
            "id": user.id, "username": user.username, "role": user.role,
            "message": "Registration completed. Merchant stores and captain accounts require administrator review/activation.",
            "approval_status": "pending" if role == "captain" else None,
            "store_status": "pending_activation" if role == "merchant" else None,
        }, status=201)

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

class AccountProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        if "profile_image" in request.FILES:
            image = request.FILES["profile_image"]
            if image.size > 5 * 1024 * 1024:
                raise ValidationError({"profile_image": "Image must be 5 MB or smaller."})
            try:
                serializers.ImageField().run_validation(image)
            except serializers.ValidationError:
                raise ValidationError({"profile_image": "The uploaded file is not a valid image."})
            if user.profile_image:
                user.profile_image.delete(save=False)
            user.profile_image = image
        if request.data.get("remove_profile_image") == "true":
            if user.profile_image:
                user.profile_image.delete(save=False)
            user.profile_image = None
        user.save()
        return Response(UserSerializer(user, context={"request": request}).data)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        current = str(request.data.get("current_password", ""))
        new_password = str(request.data.get("new_password", ""))
        if not request.user.check_password(current):
            raise ValidationError({"current_password": "Current password is incorrect."})
        if len(new_password) < 8:
            raise ValidationError({"new_password": "New password must contain at least 8 characters."})
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(new_password, request.user)
        except Exception as exc:
            raise ValidationError({"new_password": list(getattr(exc, "messages", [str(exc)]))})
        request.user.set_password(new_password)
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        return Response({"ok": True, "message": "Password changed successfully."})


class MerchantProfileSelfView(APIView):
    permission_classes = [IsAuthenticated]

    def get_profile(self, request):
        if request.user.role != "merchant":
            raise PermissionDenied("Merchant account required.")
        try:
            return MerchantProfile.objects.get(user=request.user)
        except MerchantProfile.DoesNotExist:
            raise NotFound("Store profile has not been created for this account.")

    def get(self, request):
        profile = self.get_profile(request)
        return Response(MerchantProfileSerializer(profile, context={"request": request}).data)

    def patch(self, request):
        profile = self.get_profile(request)
        # Merchants may prepare/edit their draft store before subscription activation.
        # Public visibility remains gated by MerchantViewSet and subscription state.
        serializer = MerchantProfileSerializer(profile, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MerchantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MerchantPublicSerializer
    permission_classes = [IsAuthenticated]
    queryset = MerchantProfile.objects.all()
    def get_queryset(self):
        today = timezone.localdate()
        return self.queryset.filter(is_open=True).filter(
            Q(user__subscription_required=False) |
            Q(user__subscriptions__status="active", user__subscriptions__starts_on__lte=today, user__subscriptions__ends_on__gte=today)
        ).distinct().order_by("shop_name")

def subscription_access_error(user):
    """Enforce the same subscription state exposed to captain and admin APIs."""
    state = subscription_state(user)
    if state["active"]:
        return None
    if user.role == "captain":
        CaptainProfile.objects.filter(user=user, online=True).update(online=False)
    elif user.role == "merchant":
        MerchantProfile.objects.filter(user=user, is_open=True).update(is_open=False)
    return "Your subscription is not active. Please contact Waselni administration to renew it."


def add_months(source, months):
    month = source.month - 1 + months
    year = source.year + month // 12
    month = month % 12 + 1
    day = min(source.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class AdminUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def check_admin(self, request):
        if request.user.role != "admin" and not request.user.is_superuser:
            raise PermissionDenied("Only the platform administrator can manage accounts.")

    def get(self, request):
        self.check_admin(request)
        rows = []
        users = (User.objects.exclude(role="admin").select_related("captain_profile")
                 .prefetch_related("subscriptions__payments").order_by("-date_joined"))
        for user in users:
            state = subscription_state(user)
            latest = max(user.subscriptions.all(), key=lambda x: (x.starts_on, x.id), default=None)
            current = state["subscription"]
            rows.append({
                "id": user.id, "username": user.username, "identity_number": user.identity_number or "",
                "first_name": user.first_name, "last_name": user.last_name, "name": user.get_full_name() or user.username,
                "phone": user.phone, "role": user.role, "is_active": user.is_active,
                "subscription_required": state["required"],
                "subscription_active": state["active"],
                "subscription_status": state["status"],
                "subscription": current,
                "last_subscription": ({"id": latest.id, "amount": str(latest.amount), "ends_on": latest.ends_on.isoformat(), "status": latest.status} if latest else None),
                "captain_profile_id": getattr(getattr(user, "captain_profile", None), "id", None) if user.role == "captain" else None,
                "eligibility": evaluate_captain(user) if user.role == "captain" else None,
            })
        return Response(rows)

    def post(self, request):
        self.check_admin(request)
        data = request.data
        role = data.get("role")
        if role not in ("customer", "merchant", "captain"):
            raise ValidationError({"role": "Choose customer, merchant or captain. Admin accounts are not created here."})
        identity = str(data.get("identity_number", "")).strip()
        first = str(data.get("first_name", "")).strip()
        last = str(data.get("last_name", "")).strip()
        phone = str(data.get("phone", "")).strip()
        if not identity or not first or not phone:
            raise ValidationError("Identity number, first name and phone are required.")
        if User.objects.filter(identity_number=identity).exists() or User.objects.filter(username=identity).exists():
            raise ValidationError({"identity_number": "An account already exists for this identity number."})
        shop_name = str(data.get("shop_name", "")).strip()
        if role == "merchant" and not shop_name:
            raise ValidationError({"shop_name": "Store name is required for a merchant account."})
        raw_password = str(data.get("password", "")).strip() or secrets.token_urlsafe(9)
        if len(raw_password) < 8:
            raise ValidationError({"password": "Temporary password must contain at least 8 characters."})
        with transaction.atomic():
            user = User.objects.create_user(username=identity, password=raw_password, first_name=first, last_name=last,
                phone=phone, identity_number=identity, role=role, language=data.get("language", "ar"),
                subscription_required=bool(data.get("subscription_required", role in ("merchant", "captain"))),
                must_change_password=True)
            if role == "merchant":
                MerchantProfile.objects.create(user=user, shop_name=shop_name, category="general", is_open=False)
            elif role == "captain":
                vehicle_type = data.get("vehicle_type", "motorcycle")
                permit_type = data.get("permit_type", "west_bank")
                if vehicle_type not in dict(CaptainProfile.VEHICLES):
                    raise ValidationError({"vehicle_type": "Choose a valid vehicle type."})
                if permit_type not in dict(CaptainProfile.PERMITS):
                    raise ValidationError({"permit_type": "Choose a valid permit type."})
                CaptainProfile.objects.create(
                    user=user, approved=False, online=False,
                    vehicle_type=vehicle_type,
                    vehicle_model=str(data.get("vehicle_model", "")).strip()[:100],
                    plate_number=str(data.get("plate_number", "")).strip()[:30],
                    permit_type=permit_type,
                    checkpoint_badge=bool(data.get("checkpoint_badge", False)),
                    license_verified=False, insurance_verified=False,
                )
        return Response({"id": user.id, "username": user.username, "identity_number": identity,
                         "temporary_password": raw_password, "role": user.role,
                         "subscription_required": user.subscription_required,
                         "message": "Account created. Share the temporary password securely with the user."}, status=201)


class AdminSubscriptionsView(APIView):
    """Central subscription ledger used only by the in-app React admin console."""
    permission_classes = [IsAuthenticated]

    def check_admin(self, request):
        if request.user.role != "admin" and not request.user.is_superuser:
            raise PermissionDenied("Only the platform administrator can manage subscriptions.")

    def get(self, request):
        self.check_admin(request)
        today = timezone.localdate()
        rows = []
        qs = Subscription.objects.select_related("user").prefetch_related("payments").order_by("-created_at")
        for sub in qs:
            paid = sum((payment.amount for payment in sub.payments.all()), Decimal("0.00"))
            due = sub.amount * sub.months
            effective = classify_subscription(sub, today)
            is_current = effective == "active"
            rows.append({
                "id": sub.id, "user_id": sub.user_id, "username": sub.user.username,
                "name": sub.user.get_full_name() or sub.user.username, "role": sub.user.role,
                "account_active": sub.user.is_active, "required": sub.user.subscription_required,
                "amount": str(sub.amount), "currency": sub.currency, "months": sub.months,
                "total_due": str(due), "paid_total": str(paid), "remaining": str(max(due - paid, Decimal("0.00"))),
                "starts_on": sub.starts_on.isoformat(), "ends_on": sub.ends_on.isoformat(),
                "status": sub.status, "effective_status": effective, "is_current": is_current, "notes": sub.notes,
            })
        return Response(rows)

    def patch(self, request, subscription_id):
        self.check_admin(request)
        try:
            sub = Subscription.objects.select_related("user").get(pk=subscription_id)
        except Subscription.DoesNotExist:
            return Response({"detail": "Subscription not found."}, status=404)
        status = request.data.get("status")
        if status not in dict(Subscription.STATUS_CHOICES):
            raise ValidationError({"status": "Choose active, pending, expired or cancelled."})
        sub.status = status
        sub.save(update_fields=["status"])
        sub.user.subscription_required = True
        sub.user.save(update_fields=["subscription_required"])
        publish_captain_eligibility(sub.user)  # also forces the captain offline if no longer eligible
        state = subscription_state(sub.user)
        return Response({"ok": True, "subscription_id": sub.id, "status": sub.status,
                         "subscription_active": state["active"], "subscription_status": state["status"], "user_id": sub.user_id})


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def check_admin(self, request):
        if request.user.role != "admin" and not request.user.is_superuser:
            raise PermissionDenied("Only the platform administrator can manage accounts.")
    def patch(self, request, user_id):
        self.check_admin(request)
        try: user = User.objects.get(pk=user_id)
        except User.DoesNotExist: return Response({"detail": "User not found."}, status=404)
        if "is_active" in request.data: user.is_active = as_bool(request.data["is_active"])
        if "subscription_required" in request.data: user.subscription_required = as_bool(request.data["subscription_required"])
        if "phone" in request.data: user.phone = str(request.data["phone"]).strip()
        user.save()
        publish_captain_eligibility(user)
        return Response({"ok": True, "is_active": user.is_active, "subscription_required": user.subscription_required})


class AdminUserSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, user_id):
        if request.user.role != "admin" and not request.user.is_superuser:
            raise PermissionDenied("Only the platform administrator can manage subscriptions.")
        try: user = User.objects.get(pk=user_id)
        except User.DoesNotExist: return Response({"detail": "User not found."}, status=404)
        try:
            amount = Decimal(str(request.data.get("amount", "")))
            months = int(request.data.get("months", 1))
            starts_on = date.fromisoformat(str(request.data.get("starts_on") or timezone.localdate().isoformat()))
        except Exception:
            raise ValidationError("Enter a valid amount, start date and duration.")
        if amount <= 0 or months < 1 or months > 24:
            raise ValidationError("Monthly amount must be greater than zero and duration must be 1–24 months.")
        ends_on = add_months(starts_on, months) - timedelta(days=1)
        status = request.data.get("status", "active")
        if status not in ("active", "pending"):
            raise ValidationError({"status": "New subscriptions can be active or pending."})
        with transaction.atomic():
            user.subscription_required = True
            user.save(update_fields=["subscription_required"])
            sub = Subscription.objects.create(user=user, amount=amount, months=months, currency="ILS", starts_on=starts_on,
                ends_on=ends_on, status=status, notes=str(request.data.get("notes", ""))[:500], created_by=request.user)
        publish_captain_eligibility(user)
        return Response({"id": sub.id, "amount": str(sub.amount), "months": sub.months, "total_due": str(sub.amount * sub.months), "starts_on": sub.starts_on.isoformat(),
                         "ends_on": sub.ends_on.isoformat(), "status": sub.status}, status=201)


class AdminSubscriptionPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, subscription_id):
        if request.user.role != "admin" and not request.user.is_superuser:
            raise PermissionDenied("Only the platform administrator can record payments.")
        try: sub = Subscription.objects.get(pk=subscription_id)
        except Subscription.DoesNotExist: return Response({"detail": "Subscription not found."}, status=404)
        try: amount = Decimal(str(request.data.get("amount", "")))
        except Exception: raise ValidationError({"amount": "Enter a valid payment amount."})
        if amount <= 0: raise ValidationError({"amount": "Payment must be greater than zero."})
        paid = sum((p.amount for p in sub.payments.all()), Decimal("0.00"))
        remaining = (sub.amount * sub.months) - paid
        if amount > remaining: raise ValidationError({"amount": f"Payment exceeds the remaining balance ({remaining})."})
        payment = SubscriptionPayment.objects.create(subscription=sub, amount=amount,
            method=request.data.get("method", "cash"), reference=str(request.data.get("reference", ""))[:100],
            notes=str(request.data.get("notes", ""))[:500], recorded_by=request.user)
        return Response({"id": payment.id, "amount": str(payment.amount), "paid_at": payment.paid_at.isoformat()}, status=201)


def captain_status_row(profile, elig):
    """One payload shape for the captain dashboard AND the admin dashboard.

    Both IDs are explicit: ``user_id`` is the account, ``captain_profile_id`` is
    the CaptainProfile row.  ``id`` is kept only as a deprecated alias of the
    profile id for old clients.  Every status field is derived from ``elig``.
    """
    user = profile.user
    return {
        "id": profile.id, "captain_profile_id": profile.id, "user_id": user.id,
        "username": user.username, "name": user.get_full_name() or user.username,
        "vehicle_type": profile.vehicle_type, "vehicle_model": profile.vehicle_model,
        "plate_number": profile.plate_number, "permit_type": profile.permit_type,
        "checkpoint_badge": profile.checkpoint_badge,
        "license_verified": profile.license_verified, "insurance_verified": profile.insurance_verified,
        "documents": {"identity_uploaded": bool(profile.identity_document),
                      "license_uploaded": bool(profile.driving_license_document),
                      "insurance_uploaded": bool(profile.insurance_document),
                      "undertaking_signed": bool(profile.digital_undertaking_signed_at)},
        "current_latitude": profile.current_latitude, "current_longitude": profile.current_longitude,
        "approval_status": elig["approval"]["status"],
        "eligibility": elig,
        **legacy_fields(elig),
    }


class CaptainSelfView(APIView):
    permission_classes = [IsAuthenticated]

    def get_profile(self, request):
        if request.user.role != "captain":
            raise PermissionDenied("Captain account required.")
        try:
            return request.user.captain_profile
        except CaptainProfile.DoesNotExist:
            raise PermissionDenied("Captain profile has not been created by an administrator.")

    def get(self, request):
        p = self.get_profile(request)
        elig = enforce_online_invariant(p)
        return Response(captain_status_row(p, elig))

    def patch(self, request):
        p = self.get_profile(request)
        elig = enforce_online_invariant(p)
        if "online" in request.data:
            if as_bool(request.data["online"]):
                if not elig["can_go_online"]:
                    return Response({"detail": elig["message"], "reason": elig["reason"], "eligibility": elig}, status=403)
                p.online = True
            else:
                p.online = False
        for field in ("identity_document", "driving_license_document", "insurance_document"):
            upload = request.FILES.get(field)
            if upload:
                if upload.size > 10 * 1024 * 1024 or not upload.name.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
                    raise ValidationError({field: "Upload a PDF, JPG or PNG file up to 10 MB."})
                setattr(p, field, upload)
        for field in ("current_latitude", "current_longitude"):
            if field in request.data:
                setattr(p, field, request.data[field] or None)
        p.save()
        return self.get(request)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.select_related("merchant").all()
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == "merchant":
            return qs.filter(merchant__user=self.request.user)
        qs = qs.filter(available=True, merchant__is_open=True)
        merchant_id = self.request.query_params.get("merchant")
        return qs.filter(merchant_id=merchant_id) if merchant_id else qs
    def perform_create(self, serializer):
        if self.request.user.role != "merchant":
            raise PermissionDenied("Only merchants can add products.")
        profile = MerchantProfile.objects.get(user=self.request.user)
        serializer.save(merchant=profile)
    def perform_update(self, serializer):
        if self.request.user.role != "merchant": raise PermissionDenied("Only merchants can edit products.")
        serializer.save()
    def perform_destroy(self, instance):
        if self.request.user.role != "merchant": raise PermissionDenied("Only merchants can delete products.")
        instance.delete()

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.select_related("customer", "merchant__user", "captain__user").all()
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        u = self.request.user
        if u.role == "admin":
            return self.queryset
        if u.role == "merchant":
            return self.queryset.filter(merchant__user=u)
        if u.role == "captain":
            return self.queryset.filter(captain__user=u)
        return self.queryset.filter(customer=u)

    def create(self, request, *args, **kwargs):
        error = subscription_access_error(request.user)
        if error:
            raise PermissionDenied(error)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_key = request.headers.get("Idempotency-Key", "").strip()[:64]
        if request_key:
            order, created = Order.objects.get_or_create(
                customer=request.user, request_key=request_key,
                defaults=serializer.validated_data,
            )
        else:
            order = serializer.save(customer=request.user)
            created = True
        if created:
            publish_order_event(order, "order.created")
        return Response(self.get_serializer(order).data, status=201 if created else 200)

    @action(detail=False, methods=["get"])
    def available(self, request):
        if request.user.role != "captain":
            raise PermissionDenied("Captain account required.")
        try:
            captain = request.user.captain_profile
        except CaptainProfile.DoesNotExist:
            return Response([])
        # Ineligible or offline captains see no dispatchable orders; the captain
        # dashboard shows the exact reason from the same eligibility result.
        if not enforce_online_invariant(captain)["can_receive_orders"]:
            return Response([])
        qs = self.queryset.filter(Q(status="ready", captain__isnull=True) | Q(status="new", order_type="ride", captain__isnull=True) | Q(captain=captain))
        orders = [o for o in qs if o.captain_id == captain.id or not order_compatibility_reasons(captain, o)]
        return Response(self.get_serializer(orders, many=True).data)

    @action(detail=False, methods=["post"], url_path="ride")
    def ride(self, request):
        if request.user.role != "customer":
            raise PermissionDenied("Only customers can request a ride.")
        error = subscription_access_error(request.user)
        if error:
            raise PermissionDenied(error)
        data = request.data
        pickup = str(data.get("pickup_address", "")).strip()
        dropoff = str(data.get("dropoff_address", "")).strip()
        if not pickup or not dropoff:
            raise ValidationError({"addresses": "Enter both pickup and destination addresses."})
        try:
            plat, plon = float(data.get("pickup_latitude")), float(data.get("pickup_longitude"))
            dlat, dlon = float(data.get("dropoff_latitude")), float(data.get("dropoff_longitude"))
        except (TypeError, ValueError):
            raise ValidationError({"location": "Select both locations using the location controls."})
        if not (-90 <= plat <= 90 and -90 <= dlat <= 90 and -180 <= plon <= 180 and -180 <= dlon <= 180):
            raise ValidationError({"location": "Coordinates are outside valid ranges."})
        # Haversine distance is a straight-line estimate; road routing requires a maps provider.
        radius = 6371.0
        a1, a2 = math.radians(plat), math.radians(dlat)
        da, do = math.radians(dlat-plat), math.radians(dlon-plon)
        h = math.sin(da/2)**2 + math.cos(a1)*math.cos(a2)*math.sin(do/2)**2
        distance = max(0.5, 2 * radius * math.asin(min(1, math.sqrt(h))) * 1.25)
        checkpoint = str(data.get("requires_checkpoint", "false")).lower() in ("true", "1", "yes")
        base_fare = Decimal(os.getenv("RIDE_BASE_FARE", "5.00"))
        per_km = Decimal(os.getenv("RIDE_PRICE_PER_KM", "2.00"))
        fee = (base_fare + (Decimal(str(distance)).quantize(Decimal("0.01")) * per_km)).quantize(Decimal("0.01"))
        checkpoint_fee = Decimal(os.getenv("RIDE_CHECKPOINT_FEE", "15.00")) if checkpoint else Decimal("0.00")
        total = fee + checkpoint_fee
        request_key = request.headers.get("Idempotency-Key", "").strip()[:64]
        order_defaults = dict(
            order_type="ride", required_vehicle="motorcycle", status="new",
            pickup_address=pickup, dropoff_address=dropoff,
            pickup_latitude=plat, pickup_longitude=plon, dropoff_latitude=dlat, dropoff_longitude=dlon,
            distance_km=Decimal(str(distance)).quantize(Decimal("0.01")), delivery_fee=fee,
            checkpoint_fee=checkpoint_fee, total=total, requires_checkpoint=checkpoint,
            payment_method=data.get("payment_method", "cash") if data.get("payment_method") in ("cash", "online") else "cash")
        if request_key:
            order, created = Order.objects.get_or_create(
                customer=request.user, request_key=request_key, defaults=order_defaults
            )
        else:
            order = Order.objects.create(customer=request.user, **order_defaults)
            created = True
        if created:
            publish_order_event(order, "order.created")
        return Response(self.get_serializer(order).data, status=201 if created else 200)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        if request.user.role != "merchant":
            raise PermissionDenied("Merchant account required.")
        error = subscription_access_error(request.user)
        if error: raise PermissionDenied(error)
        minutes = request.data.get("prep_minutes", 10)
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid preparation time."}, status=400)
        if minutes not in [10, 15, 20, 30, 40]:
            return Response({"detail": "Choose a valid preparation time."}, status=400)
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("merchant__user", "customer").get(pk=pk)
            if not order.merchant or order.merchant.user_id != request.user.id:
                raise PermissionDenied("This order does not belong to your store.")
            if order.status != "new":
                return Response({"detail": "This order is no longer new."}, status=409)
            order.prep_minutes = minutes
            order.status = "preparing"
            order.accepted_at = timezone.now()
            order.save()
        publish_order_event(order)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def arrive(self, request, pk=None):
        if request.user.role != "captain":
            raise PermissionDenied("Only the assigned captain can report arrival.")
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("captain__user", "merchant").get(pk=pk)
            if not order.captain or order.captain.user_id != request.user.id:
                raise PermissionDenied("This order is not assigned to you.")
            if order.order_type != "store" or order.status != "assigned":
                raise ValidationError("Arrival can only be reported for an assigned store order.")
            if not order.merchant_arrived_at:
                order.merchant_arrived_at = timezone.now()
                order.save(update_fields=["merchant_arrived_at", "updated_at"])
        publish_order_event(order, "order.captain_arrived")
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        new_status = request.data.get("status")
        # Existing assigned/in-progress orders may be completed even after a subscription expires.
        transitions = {
            "merchant": {"preparing": {"ready"}},
            "captain": {"assigned": {"picked_up"}, "picked_up": {"delivering"}, "delivering": {"completed"}},
            "admin": {"new": {"cancelled"}, "preparing": {"cancelled"}, "ready": {"cancelled"}, "assigned": {"cancelled"}},
            "customer": {"new": {"cancelled"}},
        }
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("merchant__user", "captain__user", "customer").get(pk=pk)
            role = request.user.role
            if role == "merchant" and (not order.merchant or order.merchant.user_id != request.user.id):
                raise PermissionDenied("This order does not belong to your store.")
            if role == "captain" and (not order.captain or order.captain.user_id != request.user.id):
                raise PermissionDenied("This order is not assigned to you.")
            if role == "customer" and order.customer_id != request.user.id:
                raise PermissionDenied("This order does not belong to you.")
            if new_status not in transitions.get(role, {}).get(order.status, set()):
                return Response({"detail": "This status transition is not allowed."}, status=400)
            if new_status == "picked_up" and order.order_type == "store" and not order.merchant_arrived_at:
                return Response({"detail": "Report arrival at the merchant before confirming pickup."}, status=400)
            if new_status == "delivering" and order.order_type == "store" and order.payment_method == "cash":
                settlement = getattr(order, "settlement", None)
                if not settlement or not settlement.closed:
                    return Response({"detail": "Both merchant and captain must confirm the immediate cash settlement before delivery starts."}, status=409)
            order.status = new_status
            if new_status == "ready":
                order.ready_at = timezone.now()
            order.save()
            if new_status == "picked_up" and order.order_type == "store" and order.payment_method == "cash" and order.merchant_id and order.captain_id:
                CashSettlement.objects.get_or_create(
                    order=order,
                    defaults={"merchant": order.merchant, "captain": order.captain,
                              "amount": order.subtotal, "reference": uuid.uuid4().hex[:12].upper()},
                )
        publish_order_event(order, "order.ready" if new_status == "ready" else "order.updated")
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        if request.user.role != "captain":
            raise PermissionDenied("Captain account required.")
        try:
            captain = request.user.captain_profile
        except CaptainProfile.DoesNotExist:
            raise PermissionDenied("Captain profile not found.")
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("merchant__user", "customer").get(pk=pk)
            eligible_status = order.status == "new" if order.order_type == "ride" else order.status == "ready"
            if not eligible_status or order.captain_id is not None:
                return Response({"detail": "Order is no longer available."}, status=409)
            elig = evaluate_captain(request.user, captain, order=order)
            if not elig["can_accept_order"]:
                return Response({"detail": elig["message"], "reason": elig["reason"], "eligibility": elig}, status=403)
            order.captain = captain
            order.status = "assigned"
            order.save()
        publish_order_event(order)
        return Response(self.get_serializer(order).data)

class SettlementViewSet(viewsets.ModelViewSet):
    serializer_class = SettlementSerializer
    permission_classes = [IsAuthenticated]
    queryset = CashSettlement.objects.select_related("order", "merchant", "captain").all()
    def get_queryset(self):
        u = self.request.user
        if u.role == "admin": return self.queryset
        if u.role == "merchant": return self.queryset.filter(merchant__user=u)
        if u.role == "captain": return self.queryset.filter(captain__user=u)
        return self.queryset.none()
    def create(self, request, *args, **kwargs):
        order_id = request.data.get("order")
        try:
            order = Order.objects.get(pk=order_id, payment_method="cash", status__in=["assigned", "picked_up", "delivering", "completed"])
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Eligible cash order not found."}, status=404)
        if not order.merchant or not order.captain: return Response({"detail": "Order needs a merchant and captain."}, status=400)
        if request.user.role not in ["admin", "merchant", "captain"]: raise PermissionDenied()
        obj, _ = CashSettlement.objects.get_or_create(order=order, defaults={"merchant": order.merchant, "captain": order.captain, "amount": order.subtotal, "reference": uuid.uuid4().hex[:12].upper()})
        return Response(self.get_serializer(obj).data, status=201)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        with transaction.atomic():
            try:
                obj = CashSettlement.objects.select_for_update().select_related("merchant__user", "captain__user").get(pk=pk)
            except CashSettlement.DoesNotExist:
                raise NotFound("Cash settlement not found.")
            role = request.user.role
            if role == "merchant" and obj.merchant.user_id == request.user.id:
                if not obj.closed: obj.confirmed_by_merchant = True
            elif role == "captain" and obj.captain.user_id == request.user.id:
                if not obj.closed: obj.confirmed_by_captain = True
            elif role != "admin":
                raise PermissionDenied("Not allowed.")
            obj.closed = obj.confirmed_by_merchant and obj.confirmed_by_captain
            if obj.closed and not obj.closed_at: obj.closed_at = timezone.now()
            obj.save(update_fields=["confirmed_by_merchant", "confirmed_by_captain", "closed", "closed_at"])
        return Response(self.get_serializer(obj).data)

class DelayReportViewSet(viewsets.ModelViewSet):
    serializer_class = DelayReportSerializer
    permission_classes = [IsAuthenticated]
    queryset = DelayReport.objects.all()
    http_method_names = ["get", "post", "head", "options"]
    def get_queryset(self):
        if self.request.user.role == "admin": return self.queryset
        if self.request.user.role == "captain": return self.queryset.filter(captain__user=self.request.user)
        return self.queryset.none()
    def perform_create(self, serializer):
        if self.request.user.role != "captain":
            raise PermissionDenied("Only captains can report merchant delays.")
        captain = CaptainProfile.objects.get(user=self.request.user)
        order = serializer.validated_data.get("order")
        if not order or order.captain_id != captain.id or order.order_type != "store":
            raise ValidationError({"order": "Choose a store order assigned to you."})
        if not order.merchant_arrived_at:
            raise ValidationError({"order": "Report your arrival first."})
        elapsed = (timezone.now() - order.merchant_arrived_at).total_seconds()
        if elapsed < 10 * 60:
            remaining = max(1, math.ceil((10 * 60 - elapsed) / 60))
            raise ValidationError({"detail": f"The free waiting period has not ended. {remaining} minute(s) remain."})
        if DelayReport.objects.filter(order=order, captain=captain).exists():
            raise ValidationError({"order": "A delay report already exists for this order."})
        serializer.save(captain=captain, arrived_at=order.merchant_arrived_at,
                        wait_minutes=max(10, math.floor(elapsed / 60)))

class SupportTicketViewSet(viewsets.ModelViewSet):
    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated]
    queryset = SupportTicket.objects.all()
    def get_queryset(self):
        return self.queryset if self.request.user.role == "admin" else self.queryset.filter(user=self.request.user)
    def perform_create(self, serializer): serializer.save(user=self.request.user)

class MerchantReportsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "merchant":
            raise PermissionDenied("Merchant account required.")
        try:
            merchant = request.user.merchant_profile
        except MerchantProfile.DoesNotExist:
            raise NotFound("Store profile not found.")
        today = timezone.localdate()
        orders = Order.objects.filter(merchant=merchant)
        today_orders = orders.filter(created_at__date=today)
        completed_today = today_orders.filter(status="completed")
        gross = completed_today.aggregate(value=Sum("total"))["value"] or Decimal("0.00")
        settlements = CashSettlement.objects.filter(merchant=merchant, created_at__date=today).select_related("captain__user", "order").order_by("-created_at")
        settlement_rows = [{
            "id": row.id, "reference": row.reference, "order_id": row.order_id,
            "captain_name": row.captain.user.get_full_name() or row.captain.user.username,
            "amount": str(row.amount), "confirmed_by_merchant": row.confirmed_by_merchant,
            "confirmed_by_captain": row.confirmed_by_captain, "closed": row.closed,
            "created_at": row.created_at.isoformat(), "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        } for row in settlements]
        return Response({
            "date": today.isoformat(), "orders_today": today_orders.count(),
            "completed_today": completed_today.count(), "gross_sales_today": str(gross),
            # Commission/subscription deductions cannot be inferred until the platform defines a rate/rule.
            "net_sales_today": None, "net_sales_note": "Commission rules are not configured; net earnings are not calculated.",
            "cash_settlements_today": settlement_rows,
            "all_orders": OrderSerializer(orders.order_by("-created_at")[:100], many=True, context={"request": request}).data,
        })


class AdminStoresView(APIView):
    permission_classes = [IsAuthenticated]

    def check_admin(self, request):
        if request.user.role != "admin" and not request.user.is_superuser:
            raise PermissionDenied("Only administrators can manage stores.")

    def get(self, request):
        self.check_admin(request)
        rows = []
        qs = MerchantProfile.objects.select_related("user").prefetch_related("products").order_by("-created_at")
        for store in qs:
            rows.append({
                "id": store.id, "user_id": store.user_id, "username": store.user.username,
                "owner_name": store.user.get_full_name() or store.user.username,
                "shop_name": store.shop_name, "category": store.category,
                "description": store.description, "address": store.address,
                "latitude": float(store.latitude) if store.latitude is not None else None,
                "longitude": float(store.longitude) if store.longitude is not None else None,
                "image": request.build_absolute_uri(store.image.url) if store.image else None,
                "cover_image": request.build_absolute_uri(store.cover_image.url) if store.cover_image else None,
                "is_open": store.is_open, "created_at": store.created_at.isoformat(),
                "product_count": store.products.count(),
                "products": [{"id": p.id, "name": p.name, "price": str(p.price),
                              "available": p.available,
                              "image": request.build_absolute_uri(p.image.url) if p.image else None}
                             for p in store.products.all()],
            })
        return Response(rows)

    def patch(self, request, store_id):
        self.check_admin(request)
        try:
            store = MerchantProfile.objects.get(pk=store_id)
        except MerchantProfile.DoesNotExist:
            raise NotFound("Store not found.")
        if "is_open" in request.data:
            store.is_open = as_bool(request.data["is_open"])
        for field in ("shop_name", "category", "description", "address", "opening_hours"):
            if field in request.data:
                setattr(store, field, str(request.data[field]).strip())
        store.save()
        return Response({"id": store.id, "is_open": store.is_open, "shop_name": store.shop_name})


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.role != "admin" and not request.user.is_superuser: return Response({"detail": "Admin only."}, status=403)
        today = timezone.localdate()
        orders = Order.objects.filter(created_at__date=today)
        return Response({
            "orders_today": orders.count(),
            "active_orders": Order.objects.filter(status__in=["new", "accepted", "preparing", "ready", "assigned", "picked_up", "delivering"]).count(),
            "completed_today": orders.filter(status="completed").count(),
            "online_captains": len(eligible_captain_user_ids()),  # online AND eligible, per the central service
            "open_merchants": MerchantProfile.objects.filter(is_open=True).count(),
            "sales_today": str(orders.filter(status="completed").aggregate(v=Sum("total"))["v"] or 0),
            "open_tickets": SupportTicket.objects.filter(status="open").count(),
        })


class AdminOperationsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.role != "admin" and not request.user.is_superuser: return Response({"detail": "Admin only."}, status=403)
        captains = []
        profiles = CaptainProfile.objects.select_related("user").prefetch_related("user__subscriptions__payments").order_by("id")
        for p in profiles:
            captains.append(captain_status_row(p, evaluate_captain(p.user, p)))
        merchants = [{"id": p.id, "user_id": p.user_id, "username": p.user.username, "shop_name": p.shop_name, "category": p.category, "address": p.address, "is_open": p.is_open} for p in MerchantProfile.objects.select_related("user").all()]
        orders = [{
            "id": o.id, "status": o.status, "customer": o.customer.username,
            "merchant": o.merchant.shop_name if o.merchant else "—",
            "merchant_name": o.merchant.shop_name if o.merchant else "—",
            "captain": o.captain.user.username if o.captain else "—",
            "total": str(o.total), "created_at": o.created_at.isoformat(),
            "pickup_address": o.pickup_address, "dropoff_address": o.dropoff_address,
            "dropoff_notes": o.dropoff_notes,
            "pickup_latitude": float(o.pickup_latitude) if o.pickup_latitude is not None else None,
            "pickup_longitude": float(o.pickup_longitude) if o.pickup_longitude is not None else None,
            "dropoff_latitude": float(o.dropoff_latitude) if o.dropoff_latitude is not None else None,
            "dropoff_longitude": float(o.dropoff_longitude) if o.dropoff_longitude is not None else None,
        } for o in Order.objects.select_related("customer", "merchant", "captain__user").order_by("-created_at")[:50]]
        tickets = [{"id": x.id, "subject": x.subject, "message": x.message, "status": x.status, "username": x.user.username, "created_at": x.created_at.isoformat()} for x in SupportTicket.objects.select_related("user").order_by("-created_at")[:50]]
        return Response({"captains": captains, "merchants": merchants, "orders": orders, "tickets": tickets})
    def patch(self, request):
        if request.user.role != "admin" and not request.user.is_superuser: return Response({"detail": "Admin only."}, status=403)
        kind, obj_id, value = request.data.get("kind"), request.data.get("id"), request.data.get("value")
        try:
            if kind == "captain":
                return Response({"detail": "Use POST /api/admin/captains/<captain_profile_id>/approval/ to change captain approval."}, status=400)
            if kind == "merchant":
                obj = MerchantProfile.objects.get(pk=obj_id); obj.is_open = bool(value); obj.save(update_fields=["is_open"])
                return Response({"ok": True, "is_open": obj.is_open})
            if kind == "ticket":
                obj = SupportTicket.objects.get(pk=obj_id); obj.status = value if value in ["open", "in_review", "resolved"] else obj.status; obj.save(update_fields=["status"])
                return Response({"ok": True, "status": obj.status})
        except (MerchantProfile.DoesNotExist, SupportTicket.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Record not found."}, status=404)
        return Response({"detail": "Unsupported operation."}, status=400)


class AdminCaptainApprovalView(APIView):
    """Explicit approval endpoint.  The URL carries the CaptainProfile id (never a user id)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, captain_profile_id):
        if request.user.role != "admin" and not request.user.is_superuser:
            raise PermissionDenied("Only the platform administrator can approve captains.")
        status = request.data.get("status")
        if status not in APPROVAL_STATUSES:
            raise ValidationError({"status": "Choose approved, rejected or pending."})
        try:
            profile = CaptainProfile.objects.select_related("user").get(pk=captain_profile_id)
        except CaptainProfile.DoesNotExist:
            return Response({"detail": "Captain profile not found."}, status=404)
        with transaction.atomic():
            set_approval(profile, status)
            if "checkpoint_badge" in request.data:
                profile.checkpoint_badge = as_bool(request.data["checkpoint_badge"])
                profile.save(update_fields=["checkpoint_badge"])
        publish_captain_eligibility(profile.user)
        profile.refresh_from_db()
        return Response({"ok": True, **captain_status_row(profile, evaluate_captain(profile.user, profile))})
