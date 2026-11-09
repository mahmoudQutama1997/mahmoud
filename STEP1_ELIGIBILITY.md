# Step 1 — Centralized captain eligibility

Single source of truth: `backend/core/services/eligibility.py`. Nothing in it approves a captain or activates a subscription.

## Verification status (be honest)
NOT executed here (no network; Django and npm packages could not be installed): `manage.py check`, `makemigrations --check`, `manage.py test`, `vite build`.
Executed here: Python byte-compilation of every backend file; TypeScript-parser syntax check of the JSX/JS; i18n key-parity check across ar/he/en; a stand-in-object harness that imported the real `eligibility.py` and ran 18 pure-logic checks (all pass; one initial failure was a harness flaw, re-verified).
Run locally: `cd backend && python manage.py makemigrations --check && python manage.py check && python manage.py test` then `cd ../frontend && npm install && npm run build`.

## API changes
- `GET/PATCH /api/captains/me/` and `GET /api/admin/operations/` (captains[]) now share one row shape (`captain_status_row`) with a nested `eligibility` object, `approval_status`, and both IDs: `user_id` and `captain_profile_id`. `id` remains as a deprecated alias of the profile id. Old flat keys (`approved`, `online`, `subscription_active`, `can_receive_orders`, ...) remain, derived from `eligibility`.
- NEW `POST /api/admin/captains/<captain_profile_id>/approval/` body `{"status": "approved"|"rejected"|"pending"}`.
- CHANGED `PATCH /api/admin/operations/` with `kind: "captain"` now returns 400 (it was the profile-id/user-id ambiguity).
- `GET /api/admin/subscriptions/` rows gain `effective_status` (active/not_started/expired/pending/cancelled); `is_current` = `effective_status == "active"`. `status` stays the administrator-stored value.
- `GET /api/admin/users/` rows gain `subscription_status`, `captain_profile_id`, `eligibility` (captains only).
- `PATCH /api/captains/me/` going online while ineligible → 403 `{detail, reason, eligibility}`. `online: "false"` strings are parsed correctly (previously truthy).
- `POST /api/orders/<id>/assign/` ineligible → 403 `{detail, reason, eligibility}`; already taken → 409.
- `GET /api/orders/available/` returns `[]` for offline/ineligible captains (previously 403 for subscription problems).
- `dashboard/summary` `online_captains` now counts online AND eligible captains.
- WebSocket: captains are no longer in a shared `role_captain` group. Dispatch events go only to captains the service approves for that order; new `captain.eligibility` messages are sent on connect and whenever an admin changes approval, account status or subscriptions.

## Database
Migration `0006_captainprofile_rejected`: adds `CaptainProfile.rejected` (BooleanField, default False). Schema-only; no existing row values are read or changed.

## Rules
Blocking: account active, role captain, profile exists, approval approved, valid vehicle type, subscription active or not required. Separate: online. Per order: vehicle match, checkpoint badge. Warning only: missing vehicle model/plate.
Subscription effective status: dates decide (a stored `active` row outside its dates is `expired`/`not_started`). Payments never change status.
