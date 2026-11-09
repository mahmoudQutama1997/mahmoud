"""Single source of truth for captain eligibility and subscription state.

Every API that needs to know "may this captain go online / see orders / accept
this order?" (captain dashboard, admin dashboard, available orders, order
assignment, WebSocket fan-out) must call ``evaluate_captain`` here instead of
re-implementing any of the rules.  Nothing in this module activates a
subscription or approves a captain; it only reads state.
"""
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from ..models import CaptainProfile

# ---------------------------------------------------------------- reasons
# Machine-readable code -> English fallback message (the React app translates
# the codes; the message is a safe default for API consumers and logs).
REASON_MESSAGES = {
    "account_inactive": "This account is suspended or inactive.",
    "not_captain": "This account does not have the captain role.",
    "profile_missing": "No captain profile exists for this account.",
    "approval_pending": "The captain profile is waiting for administrator approval.",
    "approval_rejected": "The captain application was rejected by the administration.",
    "vehicle_invalid": "A valid vehicle type is missing from the captain profile.",
    "subscription_missing": "A subscription is required but none has been recorded.",
    "subscription_pending": "The subscription is waiting for payment or activation by the administration.",
    "subscription_not_started": "The subscription has not started yet.",
    "subscription_expired": "The subscription has expired.",
    "subscription_cancelled": "The subscription was cancelled.",
    "offline": "The captain is offline.",
    "vehicle_mismatch": "This order requires a different vehicle type.",
    "checkpoint_required": "This order requires checkpoint authorization.",
}
WARNING_CODES = ("vehicle_details_incomplete",)
VALID_VEHICLES = {code for code, _ in CaptainProfile.VEHICLES}
APPROVAL_STATUSES = ("pending", "approved", "rejected")


# ----------------------------------------------------------- subscriptions
def classify_subscription(sub, today=None):
    """Effective status of one subscription row.

    Returns one of: active, not_started, expired, pending, cancelled.
    The stored ``status`` field is only the administrator's intent; dates decide
    whether an ``active`` row is really usable today.
    """
    today = today or timezone.localdate()
    if sub.status == "cancelled":
        return "cancelled"
    if sub.status == "pending":
        return "pending"
    if sub.status == "expired":
        return "expired"
    if sub.starts_on > today:
        return "not_started"
    if sub.ends_on < today:
        return "expired"
    return "active"


def subscription_details(sub, effective_status):
    paid = sum((p.amount for p in sub.payments.all()), Decimal("0.00"))
    total_due = sub.amount * sub.months
    return {
        "id": sub.id, "status": sub.status, "effective_status": effective_status,
        "starts_on": sub.starts_on.isoformat(), "ends_on": sub.ends_on.isoformat(),
        "amount": str(sub.amount), "currency": sub.currency, "months": sub.months,
        "total_due": str(total_due), "paid_total": str(paid),
        "remaining": str(max(total_due - paid, Decimal("0.00"))),
    }


def subscription_state(user, today=None):
    """Authoritative subscription decision for any user.

    ``status`` is one of: not_required, active, not_started, expired, pending,
    cancelled, missing.  ``active`` is True for ``active`` and ``not_required``.
    ``subscription`` describes the row that explains the status (or None).
    """
    today = today or timezone.localdate()
    if user.role == "admin" or not user.subscription_required:
        return {"required": False if user.role == "admin" else bool(user.subscription_required),
                "status": "not_required", "active": True, "subscription": None}
    rows = [(classify_subscription(s, today), s) for s in user.subscriptions.all()]

    def newest(items):
        return max(items, key=lambda r: (r[1].starts_on, r[1].id))

    chosen, status = None, "missing"
    for wanted in ("active", "not_started", "expired", "pending", "cancelled"):
        group = [r for r in rows if r[0] == wanted]
        if group:
            if wanted == "not_started":
                chosen = min(group, key=lambda r: (r[1].starts_on, r[1].id))
            else:
                chosen = newest(group)
            status = wanted
            break
    details = subscription_details(chosen[1], status) if chosen else None
    return {"required": True, "status": status, "active": status == "active", "subscription": details}


# ---------------------------------------------------------------- approval
def approval_status(profile):
    if profile.approved:
        return "approved"
    if profile.rejected:
        return "rejected"
    return "pending"


def set_approval(profile, status):
    """Administrator action: the only code path that changes approval."""
    if status not in APPROVAL_STATUSES:
        raise ValueError("status must be approved, rejected or pending")
    profile.approved = status == "approved"
    profile.rejected = status == "rejected"
    fields = ["approved", "rejected"]
    if status != "approved" and profile.online:
        profile.online = False
        fields.append("online")
    profile.save(update_fields=fields)
    return profile


# ------------------------------------------------------------ order rules
def order_compatibility_reasons(profile, order):
    """Per-order rules (vehicle type, checkpoint).  Empty list means compatible."""
    reasons = []
    if order.required_vehicle not in ("any", profile.vehicle_type):
        reasons.append("vehicle_mismatch")
    if order.requires_checkpoint and not profile.checkpoint_badge:
        reasons.append("checkpoint_required")
    return reasons


# ------------------------------------------------------------- evaluation
def _profile_of(user, profile):
    if profile is not None:
        return profile
    try:
        return user.captain_profile
    except ObjectDoesNotExist:
        return None


def evaluate_captain(user, profile=None, order=None, today=None):
    """Return the complete, consistent eligibility picture for a captain.

    Blocking rules (any one prevents going online / receiving orders):
    account active, captain role, profile exists, approval == approved, valid
    vehicle type, subscription satisfied (active, or not required).
    ``online`` is reported separately.  When ``order`` is given the per-order
    vehicle and checkpoint rules are applied as well.
    """
    today = today or timezone.localdate()
    profile = _profile_of(user, profile)
    role_ok = user.role == "captain"
    blockers = []
    if not user.is_active:
        blockers.append("account_inactive")
    if not role_ok:
        blockers.append("not_captain")
    if profile is None:
        blockers.append("profile_missing")

    sub = subscription_state(user, today)
    approval = approval_status(profile) if profile else "pending"
    vehicle_type = profile.vehicle_type if profile else None
    vehicle_valid = vehicle_type in VALID_VEHICLES
    online = bool(profile and profile.online)
    badge = bool(profile and profile.checkpoint_badge)

    if profile is not None:
        if approval == "rejected":
            blockers.append("approval_rejected")
        elif approval == "pending":
            blockers.append("approval_pending")
        if not vehicle_valid:
            blockers.append("vehicle_invalid")
    if not sub["active"]:
        blockers.append("subscription_" + sub["status"])

    can_go_online = not blockers
    can_receive = can_go_online and online
    reasons = list(blockers)
    if can_go_online and not online:
        reasons.append("offline")

    order_reasons = []
    vehicle_matches = checkpoint_ok = None
    if order is not None and profile is not None:
        order_reasons = order_compatibility_reasons(profile, order)
        vehicle_matches = "vehicle_mismatch" not in order_reasons
        checkpoint_ok = "checkpoint_required" not in order_reasons
        reasons += order_reasons

    warnings = []
    if profile is not None and (not profile.vehicle_model or not profile.plate_number):
        warnings.append("vehicle_details_incomplete")

    primary = reasons[0] if reasons else None
    return {
        "user_id": user.id,
        "captain_profile_id": profile.id if profile else None,
        "account": {"active": bool(user.is_active), "status": "active" if user.is_active else "inactive"},
        "role_valid": role_ok,
        "approval": {"status": approval, "approved": approval == "approved"},
        "subscription": {"required": sub["required"], "status": sub["status"],
                         "active": sub["active"], "details": sub["subscription"]},
        "online": online,
        "vehicle": {"type": vehicle_type, "valid": vehicle_valid,
                    "details_complete": "vehicle_details_incomplete" not in warnings,
                    "matches_order": vehicle_matches},
        "checkpoint": {"badge": badge,
                       "required_by_order": bool(order.requires_checkpoint) if order is not None else None,
                       "authorized": checkpoint_ok},
        "can_go_online": can_go_online,
        "can_receive_orders": can_receive,
        "can_accept_order": can_receive and not order_reasons if order is not None else can_receive,
        "reasons": reasons,
        "reason": primary,
        "message": REASON_MESSAGES.get(primary) if primary else None,
        "warnings": warnings,
    }


def legacy_fields(elig):
    """Flat keys kept so older clients keep working; derived from ``elig`` only."""
    sub = elig["subscription"]
    return {
        "account_active": elig["account"]["active"],
        "approved": elig["approval"]["approved"],
        "online": elig["online"],
        "subscription_required": sub["required"],
        "subscription_active": sub["active"],
        "subscription": sub["details"],
        "subscription_error": None if sub["active"] else REASON_MESSAGES.get("subscription_" + sub["status"]),
        "can_receive_orders": elig["can_receive_orders"],
    }


def enforce_online_invariant(profile, today=None):
    """A captain must never be stored as online while ineligible to be online."""
    result = evaluate_captain(profile.user, profile, today=today)
    if profile.online and not result["can_go_online"]:
        profile.online = False
        profile.save(update_fields=["online"])
        result = evaluate_captain(profile.user, profile, today=today)
    return result


def eligible_captain_user_ids(order=None, today=None):
    """User IDs of online captains who may receive ``order`` (or any order if None)."""
    profiles = (CaptainProfile.objects.filter(online=True, approved=True, user__is_active=True, user__role="captain")
                .select_related("user").prefetch_related("user__subscriptions__payments"))
    ids = []
    for p in profiles:
        if evaluate_captain(p.user, p, order=order, today=today)["can_accept_order"]:
            ids.append(p.user_id)
    return ids
