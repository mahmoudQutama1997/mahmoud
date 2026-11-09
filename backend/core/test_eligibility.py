"""Captain eligibility tests: service rules, API consistency, dispatch and WebSocket.

Everything here is derived from core.services.eligibility; nothing is mocked
except the clock where a date is passed explicitly.
"""
from datetime import timedelta
from decimal import Decimal

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .consumers import OrderEventsConsumer
from .models import CaptainProfile, Order, Subscription, SubscriptionPayment
from .services.eligibility import (
    classify_subscription, enforce_online_invariant, eligible_captain_user_ids,
    evaluate_captain, order_compatibility_reasons, set_approval, subscription_state,
)
from .views import publish_order_event

User = get_user_model()
TODAY = timezone.localdate()


def make_captain(username="cap", approved=True, rejected=False, online=False, required=True,
                 sub="active", vehicle="motorcycle", badge=False, active=True, model="Honda", plate="123-45"):
    """Build a captain.  ``sub`` is None or the subscription scenario to create."""
    user = User.objects.create_user(username=username, password="captain-password-123", role="captain",
                                    subscription_required=required, is_active=active)
    profile = CaptainProfile.objects.create(user=user, approved=approved, rejected=rejected, online=online,
                                            vehicle_type=vehicle, checkpoint_badge=badge,
                                            vehicle_model=model, plate_number=plate)
    spans = {
        "active": (TODAY - timedelta(days=2), TODAY + timedelta(days=20), "active"),
        "expired": (TODAY - timedelta(days=40), TODAY - timedelta(days=1), "active"),
        "future": (TODAY + timedelta(days=3), TODAY + timedelta(days=33), "active"),
        "pending": (TODAY, TODAY + timedelta(days=30), "pending"),
        "cancelled": (TODAY, TODAY + timedelta(days=30), "cancelled"),
    }
    if sub:
        start, end, status = spans[sub]
        Subscription.objects.create(user=user, amount=Decimal("35.00"), months=1,
                                    starts_on=start, ends_on=end, status=status)
    return user, profile


def make_order(**kw):
    customer = kw.pop("customer", None) or User.objects.create_user(
        username=f"cust{Order.objects.count()}-{User.objects.count()}", password="customer-password-123", role="customer")
    defaults = dict(customer=customer, order_type="store", status="ready", required_vehicle="any")
    defaults.update(kw)
    return Order.objects.create(**defaults)


class EligibilityServiceTests(TestCase):
    def test_fully_eligible_online_captain(self):
        user, profile = make_captain(online=True)
        e = evaluate_captain(user, profile)
        self.assertTrue(e["can_go_online"])
        self.assertTrue(e["can_receive_orders"])
        self.assertEqual(e["reasons"], [])
        self.assertIsNone(e["reason"])
        self.assertEqual(e["account"]["status"], "active")
        self.assertEqual(e["approval"]["status"], "approved")
        self.assertEqual(e["subscription"]["status"], "active")
        self.assertEqual(e["user_id"], user.id)
        self.assertEqual(e["captain_profile_id"], profile.id)

    def test_offline_is_separate_from_ineligible(self):
        user, profile = make_captain(online=False)
        e = evaluate_captain(user, profile)
        self.assertTrue(e["can_go_online"])
        self.assertFalse(e["can_receive_orders"])
        self.assertEqual(e["reason"], "offline")
        self.assertFalse(e["online"])

    def test_pending_approval_blocks(self):
        user, profile = make_captain(approved=False)
        e = evaluate_captain(user, profile)
        self.assertEqual(e["approval"]["status"], "pending")
        self.assertFalse(e["can_go_online"])
        self.assertEqual(e["reason"], "approval_pending")

    def test_rejected_blocks_and_is_distinct_from_pending(self):
        user, profile = make_captain(approved=False, rejected=True)
        e = evaluate_captain(user, profile)
        self.assertEqual(e["approval"]["status"], "rejected")
        self.assertEqual(e["reason"], "approval_rejected")

    def test_inactive_account_blocks_first(self):
        user, profile = make_captain(active=False, approved=False)
        e = evaluate_captain(user, profile)
        self.assertEqual(e["account"]["status"], "inactive")
        self.assertEqual(e["reasons"][0], "account_inactive")
        self.assertFalse(e["can_go_online"])

    def test_wrong_role_and_missing_profile(self):
        customer = User.objects.create_user(username="notcap", password="customer-password-123", role="customer")
        self.assertIn("not_captain", evaluate_captain(customer)["reasons"])
        no_profile = User.objects.create_user(username="noprofile", password="captain-password-123", role="captain")
        e = evaluate_captain(no_profile)
        self.assertIn("profile_missing", e["reasons"])
        self.assertIsNone(e["captain_profile_id"])
        self.assertFalse(e["can_go_online"])

    def test_subscription_not_required(self):
        user, profile = make_captain(required=False, sub=None, online=True)
        e = evaluate_captain(user, profile)
        self.assertEqual(e["subscription"]["status"], "not_required")
        self.assertFalse(e["subscription"]["required"])
        self.assertTrue(e["can_receive_orders"])

    def test_subscription_missing(self):
        user, profile = make_captain(sub=None)
        e = evaluate_captain(user, profile)
        self.assertEqual(e["subscription"]["status"], "missing")
        self.assertEqual(e["reason"], "subscription_missing")

    def test_subscription_expired_by_dates_even_if_status_active(self):
        user, profile = make_captain(sub="expired")
        e = evaluate_captain(user, profile)
        self.assertEqual(e["subscription"]["status"], "expired")
        self.assertEqual(e["reason"], "subscription_expired")
        self.assertEqual(Subscription.objects.get(user=user).status, "active")  # stored value untouched

    def test_subscription_not_started(self):
        user, profile = make_captain(sub="future")
        e = evaluate_captain(user, profile)
        self.assertEqual(e["subscription"]["status"], "not_started")
        self.assertEqual(e["reason"], "subscription_not_started")

    def test_subscription_pending_and_cancelled(self):
        u1, p1 = make_captain("c1", sub="pending")
        self.assertEqual(evaluate_captain(u1, p1)["reason"], "subscription_pending")
        u2, p2 = make_captain("c2", sub="cancelled")
        self.assertEqual(evaluate_captain(u2, p2)["reason"], "subscription_cancelled")

    def test_payment_never_activates_a_pending_subscription(self):
        user, profile = make_captain(sub="pending")
        sub = Subscription.objects.get(user=user)
        SubscriptionPayment.objects.create(subscription=sub, amount=sub.amount * sub.months)
        e = evaluate_captain(user, profile)
        self.assertFalse(e["subscription"]["active"])
        self.assertEqual(e["subscription"]["status"], "pending")
        self.assertEqual(e["subscription"]["details"]["remaining"], "0.00")

    def test_expired_with_renewal_scheduled_reports_not_started(self):
        user, profile = make_captain(sub="expired")
        Subscription.objects.create(user=user, amount=Decimal("35.00"), months=1,
                                    starts_on=TODAY + timedelta(days=2), ends_on=TODAY + timedelta(days=32), status="active")
        self.assertEqual(subscription_state(user)["status"], "not_started")

    def test_explicit_today_parameter_drives_dates(self):
        user, profile = make_captain(sub="active")
        later = TODAY + timedelta(days=60)
        self.assertEqual(evaluate_captain(user, profile, today=later)["subscription"]["status"], "expired")
        sub = Subscription.objects.get(user=user)
        self.assertEqual(classify_subscription(sub, today=TODAY), "active")

    def test_invalid_vehicle_blocks(self):
        user, profile = make_captain(vehicle="boat")
        e = evaluate_captain(user, profile)
        self.assertFalse(e["vehicle"]["valid"])
        self.assertEqual(e["reason"], "vehicle_invalid")

    def test_incomplete_vehicle_details_warn_but_do_not_block(self):
        user, profile = make_captain(model="", plate="", online=True)
        e = evaluate_captain(user, profile)
        self.assertTrue(e["can_receive_orders"])
        self.assertIn("vehicle_details_incomplete", e["warnings"])

    def test_order_vehicle_rule(self):
        user, profile = make_captain(vehicle="car", online=True)
        order = make_order(required_vehicle="motorcycle")
        e = evaluate_captain(user, profile, order=order)
        self.assertTrue(e["can_receive_orders"])
        self.assertFalse(e["can_accept_order"])
        self.assertFalse(e["vehicle"]["matches_order"])
        self.assertEqual(e["reason"], "vehicle_mismatch")
        self.assertEqual(order_compatibility_reasons(profile, order), ["vehicle_mismatch"])

    def test_order_checkpoint_rule(self):
        user, profile = make_captain(online=True, badge=False)
        order = make_order(requires_checkpoint=True)
        e = evaluate_captain(user, profile, order=order)
        self.assertFalse(e["can_accept_order"])
        self.assertEqual(e["reason"], "checkpoint_required")
        self.assertFalse(e["checkpoint"]["authorized"])
        profile.checkpoint_badge = True
        profile.save()
        e = evaluate_captain(user, profile, order=order)
        self.assertTrue(e["can_accept_order"])
        self.assertTrue(e["checkpoint"]["authorized"])

    def test_checkpoint_not_required_without_order(self):
        user, profile = make_captain(online=True, badge=False)
        e = evaluate_captain(user, profile)
        self.assertTrue(e["can_receive_orders"])
        self.assertIsNone(e["checkpoint"]["required_by_order"])

    def test_enforce_online_invariant_forces_ineligible_captain_offline(self):
        user, profile = make_captain(sub="expired", online=True)
        e = enforce_online_invariant(profile)
        profile.refresh_from_db()
        self.assertFalse(profile.online)
        self.assertFalse(e["online"])
        self.assertEqual(e["reason"], "subscription_expired")

    def test_set_approval_transitions(self):
        user, profile = make_captain(approved=False, online=False)
        set_approval(profile, "approved")
        profile.refresh_from_db()
        self.assertTrue(profile.approved)
        self.assertFalse(profile.rejected)
        profile.online = True
        profile.save()
        set_approval(profile, "rejected")
        profile.refresh_from_db()
        self.assertFalse(profile.approved)
        self.assertTrue(profile.rejected)
        self.assertFalse(profile.online)
        set_approval(profile, "pending")
        profile.refresh_from_db()
        self.assertFalse(profile.approved or profile.rejected)
        with self.assertRaises(ValueError):
            set_approval(profile, "maybe")

    def test_eligible_captain_user_ids_filters_everyone(self):
        good, _ = make_captain("good", online=True)
        make_captain("offline", online=False)
        make_captain("expired", sub="expired", online=True)
        make_captain("pending", approved=False, online=True)
        make_captain("suspended", active=False, online=True)
        make_captain("car", vehicle="car", online=True)
        order = make_order(order_type="ride", status="new", required_vehicle="motorcycle")
        self.assertEqual(eligible_captain_user_ids(order), [good.id])


class CaptainApiConsistencyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin1", password="admin-password-123", role="admin")
        self.other_user = User.objects.create_user(username="other", password="customer-password-123", role="customer")
        self.user, self.profile = make_captain("yusuf-like")
        self.client = APIClient()

    def as_admin(self):
        self.client.force_authenticate(self.admin)

    def as_captain(self, user=None):
        captain = user or self.user
        captain.refresh_from_db()
        self.client.force_authenticate(captain)

    def admin_row(self):
        self.as_admin()
        rows = self.client.get("/api/admin/operations/").data["captains"]
        return next(r for r in rows if r["captain_profile_id"] == self.profile.id)

    def test_profile_id_and_user_id_differ_and_both_are_returned(self):
        self.assertNotEqual(self.user.id, self.profile.id)  # the scenario that caused the confusion
        self.as_captain()
        me = self.client.get("/api/captains/me/").data
        self.assertEqual(me["user_id"], self.user.id)
        self.assertEqual(me["captain_profile_id"], self.profile.id)
        row = self.admin_row()
        self.assertEqual(row["user_id"], self.user.id)
        self.assertEqual(row["captain_profile_id"], self.profile.id)

    def test_admin_and_captain_dashboards_return_identical_eligibility(self):
        for scenario in ("active", "expired", "future", "pending", None):
            Subscription.objects.filter(user=self.user).delete()
            if scenario:
                make_sub = {"active": (-1, 10, "active"), "expired": (-40, -1, "active"), "future": (3, 30, "active"),
                            "pending": (0, 30, "pending")}[scenario]
                Subscription.objects.create(user=self.user, amount=Decimal("35"), months=1, status=make_sub[2],
                                            starts_on=TODAY + timedelta(days=make_sub[0]), ends_on=TODAY + timedelta(days=make_sub[1]))
            row = self.admin_row()
            self.as_captain()
            me = self.client.get("/api/captains/me/").data
            self.assertEqual(me["eligibility"], row["eligibility"], scenario)
            for key in ("approved", "subscription_active", "online", "can_receive_orders", "account_active"):
                self.assertEqual(me[key], row[key], (scenario, key))

    def test_ledger_uses_same_subscription_rules_as_captain_api(self):
        Subscription.objects.filter(user=self.user).delete()
        sub = Subscription.objects.create(user=self.user, amount=Decimal("35"), months=1, status="active",
                                          starts_on=TODAY - timedelta(days=40), ends_on=TODAY - timedelta(days=10))
        self.as_admin()
        ledger = next(r for r in self.client.get("/api/admin/subscriptions/").data if r["id"] == sub.id)
        self.assertEqual(ledger["status"], "active")           # what the administrator stored
        self.assertEqual(ledger["effective_status"], "expired")  # what the platform enforces
        self.assertFalse(ledger["is_current"])
        self.as_captain()
        me = self.client.get("/api/captains/me/").data
        self.assertEqual(me["eligibility"]["subscription"]["status"], ledger["effective_status"])

    def test_admin_users_list_exposes_both_ids_and_eligibility(self):
        self.as_admin()
        rows = self.client.get("/api/admin/users/").data
        row = next(r for r in rows if r["id"] == self.user.id)
        self.assertEqual(row["captain_profile_id"], self.profile.id)
        self.assertEqual(row["eligibility"]["user_id"], self.user.id)
        customer_row = next(r for r in rows if r["id"] == self.other_user.id)
        self.assertIsNone(customer_row["eligibility"])

    def test_approval_endpoint_uses_profile_id_and_updates_captain_view(self):
        self.profile.approved = False
        self.profile.save()
        self.as_admin()
        # Using the *user id* in the URL must not approve this captain.
        wrong = self.client.post(f"/api/admin/captains/{self.user.id}/approval/", {"status": "approved"}, format="json")
        self.assertIn(wrong.status_code, (404, 200))
        self.profile.refresh_from_db()
        if self.user.id != self.profile.id:
            self.assertFalse(self.profile.approved)
        ok = self.client.post(f"/api/admin/captains/{self.profile.id}/approval/", {"status": "approved"}, format="json")
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(ok.data["captain_profile_id"], self.profile.id)
        self.assertEqual(ok.data["user_id"], self.user.id)
        self.assertEqual(ok.data["approval_status"], "approved")
        self.as_captain()
        self.assertEqual(self.client.get("/api/captains/me/").data["approval_status"], "approved")

    def test_reject_forces_offline_and_is_reported_as_rejected(self):
        self.profile.online = True
        self.profile.save()
        self.as_admin()
        r = self.client.post(f"/api/admin/captains/{self.profile.id}/approval/", {"status": "rejected"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["eligibility"]["approval"]["status"], "rejected")
        self.assertFalse(r.data["online"])
        self.as_captain()
        me = self.client.get("/api/captains/me/").data
        self.assertEqual(me["eligibility"]["reason"], "approval_rejected")

    def test_approval_endpoint_permissions_and_validation(self):
        self.as_captain()
        self.assertEqual(self.client.post(f"/api/admin/captains/{self.profile.id}/approval/", {"status": "approved"}, format="json").status_code, 403)
        self.as_admin()
        self.assertEqual(self.client.post(f"/api/admin/captains/{self.profile.id}/approval/", {"status": "bogus"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/admin/captains/99999/approval/", {"status": "approved"}, format="json").status_code, 404)

    def test_legacy_generic_patch_no_longer_changes_captain_approval(self):
        self.profile.approved = False
        self.profile.save()
        self.as_admin()
        r = self.client.patch("/api/admin/operations/", {"kind": "captain", "id": self.profile.id, "value": True}, format="json")
        self.assertEqual(r.status_code, 400)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.approved)

    def test_admin_created_captain_is_not_auto_approved_or_subscribed(self):
        self.as_admin()
        r = self.client.post("/api/admin/users/", {"identity_number": "555000111", "first_name": "New", "phone": "0590000001",
                                                   "role": "captain", "vehicle_type": "motorcycle"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        profile = CaptainProfile.objects.get(user__identity_number="555000111")
        self.assertFalse(profile.approved)
        self.assertFalse(Subscription.objects.filter(user=profile.user).exists())
        e = evaluate_captain(profile.user, profile)
        self.assertIn("approval_pending", e["reasons"])
        self.assertIn("subscription_missing", e["reasons"])

    def test_go_online_blocked_with_reason_when_ineligible(self):
        Subscription.objects.filter(user=self.user).delete()
        self.as_captain()
        r = self.client.patch("/api/captains/me/", {"online": True}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["reason"], "subscription_missing")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.online)

    def test_go_online_and_offline_when_eligible_including_string_false(self):
        self.as_captain()
        on = self.client.patch("/api/captains/me/", {"online": True}, format="json")
        self.assertEqual(on.status_code, 200)
        self.assertTrue(on.data["online"])
        self.assertTrue(on.data["can_receive_orders"])
        off = self.client.patch("/api/captains/me/", {"online": "false"}, format="multipart")
        self.assertEqual(off.status_code, 200)
        self.assertFalse(off.data["online"])

    def test_captain_endpoint_rejects_other_roles(self):
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get("/api/captains/me/").status_code, 403)

    def test_expired_subscription_forces_online_captain_offline_on_read(self):
        Subscription.objects.filter(user=self.user).update(ends_on=TODAY - timedelta(days=1))
        self.profile.online = True
        self.profile.save()
        self.as_captain()
        me = self.client.get("/api/captains/me/").data
        self.assertFalse(me["online"])
        self.assertEqual(me["eligibility"]["reason"], "subscription_expired")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.online)

    def test_admin_suspending_account_or_cancelling_subscription_forces_offline(self):
        self.profile.online = True
        self.profile.save()
        self.as_admin()
        self.assertEqual(self.client.patch(f"/api/admin/users/{self.user.id}/", {"is_active": False}, format="json").status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.online)
        self.client.patch(f"/api/admin/users/{self.user.id}/", {"is_active": True}, format="json")
        self.profile.online = True
        self.profile.save()
        sub = Subscription.objects.get(user=self.user)
        r = self.client.patch(f"/api/admin/subscriptions/{sub.id}/", {"status": "cancelled"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["subscription_status"], "cancelled")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.online)


class DispatchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user, self.profile = make_captain("dispatch", online=True)

    def available_ids(self, user=None):
        self.client.force_authenticate(user or self.user)
        r = self.client.get("/api/orders/available/")
        self.assertEqual(r.status_code, 200)
        return [o["id"] for o in r.data]

    def test_available_lists_ready_store_order_and_new_ride(self):
        store = make_order(status="ready")
        ride = make_order(order_type="ride", status="new", required_vehicle="motorcycle")
        self.assertCountEqual(self.available_ids(), [store.id, ride.id])

    def test_available_empty_when_offline_or_ineligible(self):
        make_order()
        self.profile.online = False
        self.profile.save()
        self.assertEqual(self.available_ids(), [])
        self.profile.online = True
        self.profile.save()
        Subscription.objects.filter(user=self.user).update(status="cancelled")
        self.assertEqual(self.available_ids(), [])
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.online)

    def test_available_applies_vehicle_and_checkpoint_rules(self):
        car_only = make_order(required_vehicle="car")
        checkpoint = make_order(requires_checkpoint=True)
        plain = make_order()
        self.assertEqual(self.available_ids(), [plain.id])
        self.profile.checkpoint_badge = True
        self.profile.save()
        self.assertCountEqual(self.available_ids(), [plain.id, checkpoint.id])
        self.assertNotIn(car_only.id, self.available_ids())

    def test_assign_succeeds_once_and_second_captain_gets_409(self):
        order = make_order()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(f"/api/orders/{order.id}/assign/").status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "assigned")
        self.assertEqual(order.captain_id, self.profile.id)
        second, _ = make_captain("second", online=True)
        self.client.force_authenticate(second)
        self.assertEqual(self.client.post(f"/api/orders/{order.id}/assign/").status_code, 409)

    def test_assign_blocked_for_expired_subscription_offline_pending_and_suspended(self):
        order = make_order()
        cases = [("expired", dict(sub="expired", online=True), "subscription_expired"),
                 ("offline", dict(online=False), "offline"),
                 ("pending", dict(approved=False, online=True), "approval_pending"),
                 ("suspended", dict(active=False, online=True), "account_inactive")]
        for name, kwargs, reason in cases:
            user, profile = make_captain("a-" + name, **kwargs)
            self.client.force_authenticate(user)
            r = self.client.post(f"/api/orders/{order.id}/assign/")
            self.assertIn(r.status_code, (401, 403), name)
            if r.status_code == 403 and isinstance(r.data, dict) and "reason" in r.data:
                self.assertEqual(r.data["reason"], reason, name)
        order.refresh_from_db()
        self.assertIsNone(order.captain_id)

    def test_assign_blocked_for_vehicle_and_checkpoint_mismatch(self):
        wrong_vehicle = make_order(required_vehicle="car")
        needs_checkpoint = make_order(requires_checkpoint=True)
        self.client.force_authenticate(self.user)
        r1 = self.client.post(f"/api/orders/{wrong_vehicle.id}/assign/")
        self.assertEqual(r1.status_code, 403)
        self.assertEqual(r1.data["reason"], "vehicle_mismatch")
        r2 = self.client.post(f"/api/orders/{needs_checkpoint.id}/assign/")
        self.assertEqual(r2.status_code, 403)
        self.assertEqual(r2.data["reason"], "checkpoint_required")

    def test_non_captain_cannot_assign_or_list_available(self):
        customer = User.objects.create_user(username="cc", password="customer-password-123", role="customer")
        order = make_order()
        self.client.force_authenticate(customer)
        self.assertEqual(self.client.post(f"/api/orders/{order.id}/assign/").status_code, 403)
        self.assertEqual(self.client.get("/api/orders/available/").status_code, 403)


class WebSocketEligibilityTests(TransactionTestCase):
    """Only captains the eligibility service approves receive dispatch events."""

    async def connect(self, user):
        communicator = WebsocketCommunicator(OrderEventsConsumer.as_asgi(), "/ws/orders/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_anonymous_and_suspended_users_are_refused(self):
        communicator = WebsocketCommunicator(OrderEventsConsumer.as_asgi(), "/ws/orders/")
        communicator.scope["user"] = None
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        user, _ = await database_sync_to_async(make_captain)("ws-suspended", active=False, online=True)
        communicator, connected = await self.connect(user)
        self.assertFalse(connected)

    async def test_connect_sends_eligibility_snapshot(self):
        user, _ = await database_sync_to_async(make_captain)("ws-snapshot", online=True)
        communicator, connected = await self.connect(user)
        self.assertTrue(connected)
        message = await communicator.receive_json_from()
        self.assertEqual(message["type"], "captain.eligibility")
        self.assertTrue(message["eligibility"]["can_receive_orders"])
        await communicator.disconnect()

    async def test_only_eligible_captains_get_ready_order_events(self):
        good, _ = await database_sync_to_async(make_captain)("ws-good", online=True)
        expired, _ = await database_sync_to_async(make_captain)("ws-expired", sub="expired", online=True)
        offline, _ = await database_sync_to_async(make_captain)("ws-offline", online=False)
        comms = {}
        for name, user in (("good", good), ("expired", expired), ("offline", offline)):
            comms[name], connected = await self.connect(user)
            self.assertTrue(connected, name)
            await comms[name].receive_json_from()  # initial eligibility snapshot
        order = await database_sync_to_async(make_order)(status="ready")
        await database_sync_to_async(publish_order_event)(order, "order.ready")
        event = await comms["good"].receive_json_from()
        self.assertEqual(event["type"], "order.ready")
        self.assertEqual(event["order_id"], order.id)
        self.assertTrue(await comms["expired"].receive_nothing(timeout=0.3))
        self.assertTrue(await comms["offline"].receive_nothing(timeout=0.3))
        for c in comms.values():
            await c.disconnect()
