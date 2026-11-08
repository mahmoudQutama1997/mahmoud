# Waselni source package verification

Date: 2026-11-08

## Source audit

The supplied archive contains one Django backend and one React/Vite frontend. The frontend has four role build modes (customer, captain, merchant, admin); the first three have distinct Capacitor app IDs. All builds share the existing React source and API. The archive includes Django models, serializers, views, role checks, centralized captain eligibility, WebSocket consumers, migrations, frontend API/authentication, role routing, and prior implementation notes. No database file was present in the supplied archive, and none was created from or substituted for an existing user database.

The source includes customer store ordering and ride requests, merchant catalog and order handling, captain onboarding/eligibility/dispatch, admin account and operations management, settlements, Arabic/Hebrew/English strings, and order event notifications. This is an MVP source package, not a complete production service.

## Changes made

- Removed the unsupported 35 minute preparation option from the merchant UI and backend validation; the accepted values now match 10, 15, 20, 30, and 40 minutes.
- Added a reversible Django migration for the current order status choices. It changes field metadata and preserves order rows.
- Added production settings protections: `DEBUG=False` requires a non-default secret, and HTTPS redirects, secure session/CSRF cookies, and HSTS default on outside debug mode.
- Added a locked `package-lock.json`, configured Vite’s native config loader in build scripts, and corrected documentation about customer-only public registration.
- Added tests for customer registration, rejection of public privileged-role creation, and rejection of the unsupported preparation time.

## Verification run

Environment: Windows, Python 3.11.0, Django 5.2.19, Node.js 24.15.0, npm 11.12.1, Vite 8.3.6.

| Check | Result |
|---|---|
| `python manage.py check` | Passed: no issues |
| `python manage.py check --deploy` with `DEBUG=False` and a strong verification-only key | Passed: no issues |
| `python manage.py makemigrations --check --dry-run` | Passed: no changes detected after migration 0010 |
| `python manage.py migrate` | Passed on a disposable verification SQLite database |
| `python manage.py migrate --check` | Passed against the migrated disposable database |
| `python manage.py test` | Passed: 63 tests |
| `npm ci` | Passed; 118 packages audited, zero vulnerabilities reported |
| `npm run build:all-portals` | Passed: customer, captain, merchant, and admin builds |
| Android/iOS native compilation | Not run; native projects are not generated in the archive. iOS compilation requires macOS and Xcode. |
| End-to-end flows against a deployed shared backend | Not run; no live service credentials or deployed environment were supplied. |

The temporary test and migration databases used for verification are not included in the deliverable. The source ZIP contains no `.env`, database, media uploads, `node_modules`, or virtual environment.

## External services and incomplete production work

- Firebase push notifications require credentials and Android/iOS platform setup. The current app must not be represented as having configured push delivery.
- SMS/OTP, payment processing, masked calling/chat, and related credentials or retention policies are not present.
- Maps use public/development routing and geocoding endpoints. Ride estimates use straight-line distance; checkpoint selection is manual. Automatic checkpoint detection, road-distance pricing, full navigation, continuous background GPS, and production live operations maps remain unfinished.
- WebSocket delivery uses an in-memory channel layer. Multi-worker production deployment needs Redis and a configured Channels Redis backend.
- Uploaded files use local media storage. Production needs persistent protected media/object storage, backups, and upload/access controls.
- The three mobile builds are role-locked Capacitor wrappers around the shared React app. Separate native projects, native permission testing, device testing, and store distribution setup remain.
- Product availability is a boolean; inventory quantities are not managed. Store and product categories are string fields rather than an administrator-managed category catalog.
- Merchant net settlements/commission policy and automatic delay charges or compensation have no approved business rules and are not calculated.
- Production infrastructure, domain/TLS, monitoring, backups, privacy/legal review, and operational procedures still need configuration and review.

## Safe existing database upgrade

Back up the current SQLite file and media directory before deployment. Review the included `backend/core/migrations/0010_alter_order_status.py`; then apply migrations to the existing database with `python manage.py migrate`. This source package itself does not contain a customer database.
