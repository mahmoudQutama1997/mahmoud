# Cursor handoff — Continue Waselni app separation

You are continuing an existing Waselni project. Do not recreate the platform from scratch and do not replace the shared Django backend.

## Approved decisions

- Android + iOS.
- One shared Django backend/API/database.
- Three separate mobile applications: Customer, Captain, Merchant.
- One separate web-only Admin Dashboard.
- Existing project and data must be preserved.

## Start here

1. Read `README.md`, `ARCHITECTURE_SPLIT_PLAN.md`, `IMPLEMENTATION_NOTES.md`, `LOCATION_MAPS_UPDATE.md`, `STEP1_ELIGIBILITY.md`, `ORDER_DUPLICATE_FIX.md`, `RIDE_MAP_AND_I18N_UPDATE.md`, `UI_FIXES_2026-11-07.md`, and `UPDATE_2026-11-06.md`.
2. Inspect the current source tree before editing. The newest baseline is the code in this ZIP.
3. Keep Django as one backend. Do not create duplicate databases or separate role-specific backends.
4. Preserve all existing models, migration history, order state transitions, idempotency, centralized captain eligibility, subscription checks, cash settlement rules, merchant location, customer delivery location, ride coordinates, and multilingual behavior.
5. The first split layer is already present: four role-specific Vite pages/build modes, role lock, customer-only public registration, and separate Capacitor configs for the three mobile apps.

## Required next implementation phases

### Phase A — Verify the split
- Install dependencies and run `npm run build:all-portals`.
- Run Django `check`, migration check, and the complete test suite.
- Fix any build/runtime issues without resetting or deleting `db.sqlite3` or existing media.
- Verify each portal rejects every other role at login and after restoring a saved session.
- Verify admin routes remain inaccessible to non-admin users at the API layer as well as in the UI.

### Phase B — Native app packaging
- Complete Capacitor Android and iOS projects for Customer, Captain, and Merchant.
- Configure the API base URL using HTTPS environment variables; never ship localhost/127.0.0.1.
- Ensure WebSocket uses WSS and the same shared API host.
- Add app-specific names, icons, splash screens, package IDs, deep links, safe-area handling, and native navigation/back-button behavior.
- Do not claim iOS builds are complete unless built with Xcode on macOS; do not claim Android builds are complete unless built with Android SDK/Gradle.

### Phase C — Native integrations
- Camera and secure document/photo upload for Captain onboarding and Merchant catalog.
- Geolocation permissions and foreground/background location strategy for Captain, with explicit privacy and battery safeguards.
- Push notifications with a real provider and server-side device-token lifecycle; do not fake Firebase success.
- Secure token storage using a supported native secure-storage plugin rather than relying on web localStorage for production native builds.
- Deep links for order details and notification taps.
- Handle offline/network recovery and WebSocket reconnects safely.

### Phase D — App-specific UX
- Customer: stores/products, checkout map, ride booking, tracking/order status, profile and support.
- Captain: eligibility state, go online/offline, eligible dispatch, accept/arrive/pickup/deliver, route/navigation links, settlements, SOS support.
- Merchant: new-order alerts, accept/preparation timer, mark ready, catalog, store hours/location, reports and settlements.
- Admin web: accounts, captain approval/documents/checkpoint badge, merchant approval/open state, subscriptions/payments, live orders/map, settlements and support.

## Non-negotiable safeguards

- Do not bypass merchant approval/open/subscription checks.
- Do not bypass captain approval, subscription, vehicle, online, or checkpoint-badge eligibility.
- Checkpoint-fee jobs must only be dispatched to badge-eligible captains.
- Do not invent road distance, automatic checkpoint detection, live tracking, VoIP, SMS, payment, or push-notification functionality when the provider integration is absent.
- Keep order creation idempotent and prevent duplicate claims/settlements.
- Keep migrations additive and data-preserving. Back up the database before any schema operation.
- Public signup is customer-only; merchant/captain accounts are provisioned by Admin.
- Never expose identity documents or private user data through public endpoints.

## Delivery expectation

Return a complete updated source ZIP, a concise change log, exact Windows commands, and an honest verification report. Clearly separate checks actually run from checks that require the user's Windows/macOS environment. Do not provide only snippets or a mockup.
