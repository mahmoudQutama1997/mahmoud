# Waselni — Separate Apps Architecture (Android + iOS, Shared Backend)

## Decision

- Platforms: Android and iOS.
- Backend: one shared Django REST API, one identity system, and one database.
- Deliverables: three separately branded/installable mobile apps (Customer, Captain, Merchant) plus a separate Admin web portal.
- Native packaging: Capacitor is used to package each isolated portal build for Android and iOS while retaining the existing React feature implementation during the separation phase.

## What this source update implements

1. Adds four independent Vite build modes (`customer`, `captain`, `merchant`, `admin`) that package the shared UI shell into separate app-specific output directories, each with its own `index.html`.
2. Adds four build modes and output folders:
   - `frontend/dist/customer`
   - `frontend/dist/captain`
   - `frontend/dist/merchant`
   - `frontend/dist/admin`
3. Adds app-role locking. A Customer build rejects merchant/captain/admin logins; the Captain, Merchant, and Admin builds similarly accept only their own account role.
4. Restricts public registration in both the frontend and Django API to customer accounts. Merchant and captain accounts must be created by the platform administrator, consistent with the central account-management workflow.
5. Adds separate Capacitor app IDs/configurations for Customer, Captain, and Merchant. Admin remains a standalone web portal and is not packaged as a mobile app.
6. Updates WebSocket URL construction so a native build can connect to the same remote Django API when `VITE_API_URL` is configured as an absolute HTTPS URL.
7. Keeps the shared backend, models, database, existing API contracts, order logic, eligibility, subscriptions, settlements, maps, and existing React feature components in place.

## Build each independent portal

From `frontend/`:

```bash
npm install
npm run build:customer
npm run build:captain
npm run build:merchant
npm run build:admin
```

Or build all four in sequence:

```bash
npm run build:all-portals
```

For local development, use one portal at a time:

```bash
npm run dev:customer
npm run dev:captain
npm run dev:merchant
npm run dev:admin
```

The existing `npm run dev` and `npm run build` remain available for the legacy combined portal during transition.

## Configure mobile API access before native packaging

A phone cannot use the developer computer's relative `/api` URL. Before building native binaries, create the relevant mode environment file (`.env.customer`, `.env.captain`, `.env.merchant`) based on its `.env.<role>.example` file and set:

```env
VITE_API_URL=https://YOUR-API-DOMAIN/api
```

Use a real HTTPS API host. Do not ship a phone build pointing at `127.0.0.1`, `localhost`, or a temporary LAN address. Configure Django `ALLOWED_HOSTS`, HTTPS, CORS, WebSocket/WSS, media storage, and production secrets for that domain.

## Capacitor setup

After installing the root frontend packages (`npm install`), install the Capacitor packages in each native app directory and build the relevant portal:

```bash
# Install each native wrapper package once
npm install --prefix native/customer
npm install --prefix native/captain
npm install --prefix native/merchant

# First time only — add native projects
npm run cap:customer:add:android
npm run cap:customer:add:ios

# After subsequent web changes
npm run cap:customer:sync
```

Equivalent `cap:*` scripts exist for Captain and Merchant. Android builds require Android Studio/Android SDK. iOS builds require macOS and Xcode. Each app has a separate application ID and its own native project directory under `frontend/native/<role>/`. Admin is deployed as a web application.

## Important architecture boundary

This is the safe first separation layer, not a claim that every screen has already been rewritten as native React Native UI. The three mobile packages currently embed their role-locked React portal using Capacitor. Continue migrating high-value phone interactions to native Capacitor plugins/components incrementally (camera/document upload, push notifications, geolocation/background location, deep links, secure storage) without changing the shared API contract unnecessarily.

## Existing capabilities intentionally retained

- Customer store browsing, checkout, delivery map, ride booking, ride history, profile and order history.
- Merchant catalog, store profile/location, orders, preparation workflow, reports and cash settlements.
- Captain onboarding/profile, document presence, approval/eligibility, checkpoint badge rules, available jobs, pickup/delivery states, route map, settlements and SOS support ticket.
- Admin account creation, captain approval, store controls, subscriptions/payments, orders, support, reports and operations map.
- Arabic/Hebrew/English UI and direction switching.
- Shared JWT authentication, REST endpoints, WebSocket events and five-second fallback refresh.

## Validation still required on the developer machine

This environment did not install npm packages or Django. After setup, run:

```bash
cd backend
python manage.py check
python manage.py makemigrations --check
python manage.py test

cd ../frontend
npm install
npm run build:all-portals
```

Then test all four roles against the same database and verify that wrong-role logins are rejected. Test native builds on Android and iOS simulators/devices, including camera/document permissions, location permission, network-loss recovery, and WebSocket reconnection.
