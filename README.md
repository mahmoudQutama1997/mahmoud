# وصلني | Waselni — Live Orders & Dispatch MVP

> **Current architecture decision (8 Nov 2026):** Android + iOS; one shared Django backend/database; separate Customer, Captain and Merchant mobile apps; separate Admin web portal. See `ARCHITECTURE_SPLIT_PLAN.md` and `CURSOR_HANDOFF.md`.

A multi-role delivery PWA starter with one shared backend and database for:
- Customer
- Merchant
- Captain
- Admin operations dashboard

The current build adds a working store-order flow, captain eligibility/availability, safe single-captain claiming, controlled order-state transitions, WebSocket order events, and a five-second REST refresh fallback.

## Stack
- Backend: Python 3.11+, Django 5.2, Django REST Framework, SimpleJWT, Django Channels + Daphne
- Frontend: React + Vite, React Router, PWA manifest/service worker
- Local database: SQLite
- Production database option: PostgreSQL via `DATABASE_URL`
- Local WebSocket channel layer: in-memory (single server process)

## Run on Windows

### 1. Backend
Open CMD inside `Waselni/backend`:

```bat
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API: http://127.0.0.1:8000/api/ (the Vite frontend proxies `/api`, `/media` and `/ws` to Django by default).  
إدارة وصلني: سجّل الدخول بحساب الإدارة من واجهة React على http://localhost:5173/admin. لا تحتاج إلى فتح Django Admin.

`daphne` is installed in `INSTALLED_APPS`, so Channels' ASGI-aware `runserver` is used for local WebSocket support.

### 2. Frontend
Open a second CMD inside `Waselni/frontend`:

```bat
npm install
npm run dev
```

Open http://localhost:5173.

## Required demo setup

To create the demo accounts and their required merchant/captain profiles in one step, run from `Waselni/backend`:

```bat
python manage.py seed_demo
```

New demo accounts use password `Demo12345!` (the platform administrator is the Django superuser you create separately):

| Role | Username |
|---|---|
| Customer | `customer1` |
| Merchant | `merchant1` |
| Demo pharmacy merchant | `merchant_pharmacy` |
| Demo electronics merchant | `merchant_electronics` |
| Captain | `captain1` |

The command is safe to run more than once: it does not duplicate users or profiles, and it does not reset passwords for accounts that already existed. It does not create an additional admin account. If an account already existed with a different password, keep using its existing password or reset it with the supported password-management workflow. `captain1` is deliberately created as not approved; approve the captain from the in-app Waselni administration dashboard before testing dispatch.

For normal platform use, sign in to the Waselni dashboard with an admin-role account and use **Admin → User management** to create accounts by identity number. The system automatically creates the matching captain profile or a closed merchant profile. Review/approve captains and open merchant stores separately. Public registration is disabled for every role.

Important: run `python manage.py createsuperuser` once to create the initial platform administrator. The account is automatically assigned the Waselni `admin` role and signs in through the React application. Operational management is handled inside Waselni, not through Django Admin.

## Live order flow

1. Customer chooses an open merchant, chooses an available product, enters quantity and delivery address, then submits an order.
2. The backend calculates item prices from the database. Delivery/checkpoint fees remain zero until the commercial pricing policy is approved.
3. The merchant sees the new order, accepts it and selects 10, 15, 20, 30 or 40 minutes for preparation.
4. The merchant marks it ready.
5. Approved, online captains see eligible ready orders. Eligibility checks vehicle requirement and checkpoint badge.
6. A captain claims an order. The database transaction and row lock prevent two captains from claiming the same order on a production database that supports row-level locking (such as PostgreSQL).
7. The assigned captain moves the order through picked_up → delivering → completed.
8. Customer, merchant, captain and admin receive order events; screens also refresh every five seconds as a fallback.

## Main API endpoints

- `POST /api/auth/register/` — disabled (accounts are created by platform administration)
- `GET/POST /api/admin/users/` — list/create identity-based accounts (admin only)
- `PATCH /api/admin/users/{id}/` — activate/deactivate account and toggle subscription requirement
- `POST /api/admin/users/{id}/subscription/` — set monthly amount, start date and duration (admin only)
- `GET /api/admin/subscriptions/` — unified subscription ledger for the in-app admin dashboard
- `PATCH /api/admin/subscriptions/{id}/` — update subscription status (admin only)
- `POST /api/admin/subscriptions/{id}/payments/` — record a manual subscription payment (admin only)
- `POST /api/account/change-password/` — mandatory first-login password change
- `POST /api/auth/token/` — obtain JWT tokens
- `GET /api/me/` — current account
- `GET /api/merchants/` — open merchants
- `GET/POST /api/products/` — browse products / merchant catalog management
- `GET/POST /api/orders/` — scoped order list / create customer order
- `GET /api/orders/available/` — eligible orders for an online captain plus their assigned orders
- `POST /api/orders/{id}/accept/` — merchant accepts and sets preparation time
- `POST /api/orders/{id}/status/` — permitted status transition
- `POST /api/orders/{id}/assign/` — captain claims a ready order
- `GET/PATCH /api/captains/me/` — captain online state, validated GPS coordinates and last-location timestamp
- `GET/POST /api/settlements/`
- `POST /api/settlements/{id}/confirm/`
- `GET/POST /api/delay-reports/`
- `GET/POST /api/support-tickets/`
- `GET /api/dashboard/summary/`
- `ws://127.0.0.1:8000/ws/orders/?token=ACCESS_TOKEN` — authenticated order events

## Notes and current boundaries

- SQLite is suitable for local development. For real concurrent captain dispatch, use PostgreSQL; SQLite does not provide equivalent row-level locking guarantees.
- The in-memory Channels layer works for a single local server process. A multi-worker deployment needs Redis and `channels_redis` as the channel layer.
- Browser WebSocket authentication uses a JWT query parameter in this MVP. Production deployments must use HTTPS/WSS and ensure access tokens are redacted from proxy/access logs.
- The dispatch filter checks online/approved status, vehicle requirement and checkpoint badge. It does not yet rank captains by live distance or ETA.
- Captain GPS is shared while the captain is online and the captain app is open; the browser watch is foreground tracking, not guaranteed background tracking after the OS suspends the app. The order API exposes the assigned captain location only to authorized order participants and the admin dashboard.
- Interactive maps use CARTO Voyager tiles, OpenStreetMap geocoding and OSRM road routing. Public endpoints are suitable for development/low-volume testing; production traffic should use a contracted provider or self-hosted services.
- Media URLs are resolved against the backend host so profile/store/product images load from separate Vercel portals. On Render, attach a persistent disk and set `MEDIA_ROOT=/var/data/media` to keep uploaded files across deploys; without persistent media storage, local uploaded files may be lost when the service restarts or redeploys.
- Push notifications, SMS, VoIP, payment gateway, live map routing, audited cash handover and production monitoring still require external integrations and security review.
- Subscription amounts are set individually by the administrator. Merchant/captain accounts require an active subscription by default; customer subscriptions can be enabled individually. Delivery and checkpoint fees remain zero until those rules are decided.
- This is an MVP development build, not a production-certified delivery service. Verify permits, insurance, safety procedures, privacy, legal and accounting requirements before any real-world launch.

## After changing models

Migration files for this release are included. For a fresh database, run `python manage.py migrate`. For an existing database created by an earlier Waselni build without recorded `core` migrations, first back up `db.sqlite3`, then run `python manage.py migrate --fake-initial`; this marks the original schema as present and applies the new account/subscription migration. Review the output carefully. Do not use `--fake-initial` if your existing `core` tables are incomplete or differ from the original MVP schema.


## Update: multilingual interface and admin control center

The frontend language selector now applies Arabic, Hebrew, and English translations across the main customer, merchant, captain, and admin screens. The document direction switches automatically (RTL for Arabic/Hebrew, LTR for English), and the selected language is saved in the browser.

The React admin control center includes live summary cards and operational sections for accounts, subscriptions and payments, captains, merchants, orders, and support tickets. Subscription state is calculated once by the backend helper and shared by the admin ledger, captain API, and dispatch checks. Admin actions include approving/revoking captain approval, opening/closing a merchant, and changing support-ticket status. These actions use the authenticated endpoint `GET/PATCH /api/admin/operations/` and require a user whose role is `admin`.

The operations map remains a clearly marked placeholder until a real maps provider and API key are configured. Frontend production builds are available through `npm run build:all-portals`.


## Central account and monthly subscription management

Public self-registration is disabled. The platform administrator creates customer, merchant and captain accounts from **Admin → Users** in the Waselni web app. The identity number is used as the login username and must be unique. Merchant creation also requires a store name; captain profiles are created automatically but remain unapproved until reviewed. A temporary password is generated if the administrator does not provide one. Share it securely; SMS/OTP delivery is not configured in this MVP.

The admin can set a separate monthly subscription amount for each account, choose its start date and duration, and record payments. Each renewal is a separate historical subscription record. Merchant and captain accounts require an active subscription by default; customers do not, unless the administrator enables **subscription required** for that account. Expired/pending subscriptions prevent merchant/captain operational actions; accounts can still sign in so the user can contact administration. Subscription approval is separate from captain/store approval.

Migration files are included. For a fresh database, run `python manage.py migrate`. For an existing database from the previous Waselni MVP, back up `db.sqlite3` and run `python manage.py migrate --fake-initial` so Django recognizes the original tables and then adds the identity and subscription fields. Inspect the migration output; do not force it if your database schema differs from the original MVP.


New accounts receive a one-time temporary password (generated by the server if the admin does not provide one) and are forced to change it at first sign-in. The MVP does not send SMS/OTP messages yet; the administrator shares the temporary password securely. The identity number is currently stored as the account username and in the restricted admin account record, so protect the database and admin credentials and use HTTPS in any deployed environment.


## Visual marketplace and image uploads (purple theme)

The merchant workspace now includes a product editor with image upload, preview, description, category and price. Product images are stored under `backend/media/products/` and are returned by the product API for merchant and customer views. The store profile page supports a logo, cover photo, description, address, category and opening hours; store images are stored under `backend/media/stores/`. Customers can choose stores and products using image cards. The interface uses a consistent purple visual theme and responsive layouts.

After updating an existing Waselni installation, activate the backend virtual environment and run:

```bat
python manage.py migrate
python manage.py runserver
```

Then, in a separate terminal, install and run the frontend:

```bat
npm install
npm run dev
```

Uploaded media is local development storage. For production, configure persistent media storage (or object storage), HTTPS, upload size/type validation, backups, and appropriate access controls before accepting public uploads.

## Shared profile photos (all account roles)

Customers, captains, merchants and administrators can manage a personal profile photo from **My Profile** (`/account`). The image is stored on the Django user record and appears in the signed-in account header and order cards. Store logo/cover images remain separate from the merchant owner's personal photo.

- Accepted formats: JPG, PNG and WebP; maximum upload size: 5 MB.
- Users can choose, preview, save or remove their photo. A default avatar is shown when no photo is set.
- API: authenticated `PATCH /api/account/profile/` using multipart form data (`profile_image=<file>`), or `remove_profile_image=true` to clear it.
- The migration adds `User.profile_image`; run `python manage.py migrate` after updating the source.
- In production, configure persistent media storage and serve `/media/` through the deployment's media/static storage setup.


## Scooter ride MVP (Phase 2)

This release adds a first working ride-request flow:
- Customer submits pickup/destination labels and browser geolocation coordinates.
- Backend estimates distance using a straight-line Haversine calculation with a 25% margin, then calculates a configurable estimate.
- A manually selected checkpoint flag adds the configured checkpoint surcharge.
- Approved, online motorcycle captains can see unassigned ride requests in `/api/orders/available/` and claim them using `/api/orders/{id}/assign/`.
- Captains advance assigned rides through picked_up, delivering, and completed.
- Customer ride history is visible in the new Ride page.

### Ride pricing configuration
Set these values in `backend/.env` before running the backend:
- `RIDE_BASE_FARE` (default 5.00 ILS)
- `RIDE_PRICE_PER_KM` (default 2.00 ILS)
- `RIDE_CHECKPOINT_FEE` (default 15.00 ILS)

The default amounts are placeholders for development and must be approved by the business before launch. Distance is not road distance. Automatic checkpoint detection, route drawing, live GPS streaming, navigation, payment collection, cancellation debt, and production maps are not included in this MVP and require additional integrations.

### Apply the ride migration
From the `backend` directory with the virtual environment active:
```bash
python manage.py migrate
```


## Ride request map interface update

The customer ride page now shows two explicit location cards: **From where should we pick you up?** and **Where are you going?**. The customer selects which point to edit, then clicks the interactive OpenStreetMap map to place that point. The pickup button can use browser geolocation (permission required; HTTPS is required outside localhost). The map starts centered on Nablus as a default view only; it does not assume that the customer is there.

The map uses Leaflet and OpenStreetMap tiles loaded from public CDNs. Address text is still entered by the customer; automatic place-name search/reverse geocoding is not configured. The backend still estimates distance as straight-line distance with a margin, not road routing. Checkpoint crossing is still a customer-selected flag and is **not automatically detected**. Do not treat the displayed fare as a production road-distance quote until a routing/geocoding provider and automatic checkpoint logic are integrated and tested.


## Captain management

Platform administrators can create captains directly from the purple Waselni admin dashboard under **Captain Management**. The form creates both the user account and its linked `CaptainProfile` in one transaction. New captains start unapproved and offline; the dashboard displays the one-time temporary password after creation. Leaving the password field empty generates a temporary password automatically. Captains can be approved from the same tab after reviewing their details.

## Captain status consistency patch (2026-11-05)

- The captain self endpoint now returns the authenticated account identity (`user_id`, `username`, and `name`) plus the effective subscription dates/status. This makes it possible to verify that the captain login matches the captain record managed by the administrator.
- Captain administration and the captain self endpoint now use the same `subscription_state()` decision: a required subscription is active only when its status is `active` and today's local date is within its start/end dates.
- The captain administration list now displays the linked user ID, approval, online state, and effective subscription state.
- The captain page refreshes its own status every five seconds and prevents starting reception unless the account is active, approved, and subscription-eligible.
- Revoking captain approval also forces the captain offline.

No database schema changes were made; no migration is required. Existing account approval and payment records are not automatically altered. After deploying, compare the `user_id`/`username` shown on the captain page with the matching row in Admin > Captain Management. Do not manually mark a subscription paid or approved unless the underlying administrative record is correct.

Validation performed for this patch: Python source compilation passed. Django tests and the Vite production build could not be run in this environment because dependencies were not installed and package-index access was unavailable. Run `python manage.py test core` in the backend virtual environment and `npm install && npm run build` in `frontend` after extracting the project.


## Latest workflow update
See `IMPLEMENTATION_NOTES.md` for captain document onboarding, checkpoint badge controls, arrival/delay enforcement, cash settlement lifecycle, merchant reports, and limitations. Apply migrations with `python manage.py migrate` from `backend/`.


## Latest source update (2026-11-06)

See `UPDATE_2026-11-06.md` for the API connectivity/auth refresh changes, UI polish, local startup instructions and verification boundaries. The frontend now uses same-origin `/api` by default; set `WASELNI_BACKEND_URL` only when Django is running on a non-default address or port.


## Separate application builds (current)

The frontend now has four role-specific entry pages and build modes. From `frontend/`, run `npm install` and then `npm run build:all-portals`. Outputs are written to `dist/customer`, `dist/captain`, `dist/merchant`, and `dist/admin`. The first three have separate Capacitor application IDs/configurations for Android and iOS; the admin portal remains web-only. See `ARCHITECTURE_SPLIT_PLAN.md` for mobile API configuration, native setup, and verification.

Public registration is customer-only. Merchant and captain accounts are created by the administrator in the Waselni dashboard. This is enforced by the Django registration endpoint, not just by hiding fields in the UI.

## Production configuration and remaining work

The `.env.example` files contain local development settings. Before deployment, set a unique `SECRET_KEY`, `DEBUG=False`, production `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, and a production `DATABASE_URL`. With `DEBUG=False`, HTTPS redirects, secure session and CSRF cookies, and HSTS are enabled by default. Terminate HTTPS at the web server or trusted proxy, and configure the proxy to set `X-Forwarded-Proto` correctly before enabling `SECURE_PROXY_SSL_HEADER` in `backend/config/settings.py`.

The local SQLite database is not included in this source archive. Existing installations should back up their database and media before applying migrations. Do not use a fresh database setup command against an existing installation.

The current source is an MVP that still needs external configuration and work before production service: push notifications require Firebase credentials and native platform setup; payments, SMS/OTP, and masked voice/chat need providers and credentials; road routing, geocoding, automated checkpoint detection, continuous background GPS, and live operations maps need production map services; production media storage, Redis-backed WebSockets, monitoring, and deployment infrastructure need setup. Ride estimates use straight-line distance and checkpoint fees are customer-selected. No iOS or Android native projects have been generated in this archive; use the Capacitor `cap:*:add:*` commands below to create them. iOS compilation requires macOS and Xcode.

## Windows verification commands

Use Python 3.11 and Node.js 20.19+ or 22.12+ for the declared toolchain. From the project root:

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test

cd ..\frontend
npm ci
npm run build:all-portals
```

For each mobile wrapper, build the matching portal first, install wrapper dependencies, add the native project once, then sync it:

```bat
npm run build:customer
npm install --prefix native\customer
npm run cap:customer:add:android
npm run cap:customer:sync
```

Repeat with `captain` or `merchant`. For iOS, use the matching `cap:<role>:add:ios` and `cap:<role>:sync:ios` commands on a Mac with Xcode. Configure `.env.customer`, `.env.captain`, and `.env.merchant` with the production HTTPS API URL before building mobile apps. Admin is a separate web build, not a mobile wrapper.

See `PRODUCTION_READINESS_REPORT.md` for the checks run against this source package and their results.
