# Waselni update — 9 Nov 2026

## Preserved
- Existing project layout, roles, authentication, API routes, order workflow, business rules, and current working-tree edits from the supplied archive.
- The original customer frontend and the separate captain/merchant/admin Vercel portal packages.

## Implemented
- Added `CaptainProfile.current_location_updated_at` and additive migration `0011_captain_location_timestamp`.
- Validated captain GPS coordinates (latitude/longitude must be sent together and remain in geographic bounds).
- Captain app shares GPS while online and foregrounded, with throttling to avoid excessive API requests.
- Authorized order responses expose current captain coordinates only while an order is assigned/picked up/delivering.
- Order maps display a moving captain marker; admin operations map displays current captain markers for active orders.
- Replaced standard OSM tiles with CARTO Voyager tiles; retained OSRM route calculation and OSM geocoding.
- Added an order progress timeline to make order cards easier to understand and follow.
- Added `mediaUrl()` so relative Django `/media/...` paths resolve against the backend origin across separate Vercel domains. Applied it to profile, store, cover, product, and order images.
- Added configurable `MEDIA_ROOT` for persistent storage deployments.
- Synchronized the updated shared frontend source into captain, merchant, and admin portal packages.

## Deployment steps
1. Deploy the backend and run `python manage.py migrate` (migration 0011 is additive).
2. On Render, attach a persistent disk and set `MEDIA_ROOT=/var/data/media` to preserve uploaded media across deploys.
3. Ensure each Vercel portal has `VITE_API_URL` set to the existing backend API URL ending in `/api`.
4. Build/deploy customer, captain, merchant and admin portals.
5. Test captain GPS permission on HTTPS with the captain app open and online; test customer/admin tracking on an active assigned order.

## Verification status
- Python `compileall`: passed.
- Frontend `node --check` for `api.js` and `i18n.js`: passed.
- Full Vite build could not run in this environment because the archived `node_modules` lacks the Linux optional native Rolldown binding. Reinstall frontend dependencies (`npm install`) in a normal Windows/Linux development environment, then run `npm run build:all-portals`.
- Django runtime checks/tests could not run because Django dependencies are not installed in the execution environment.

## Boundaries
- Browser GPS tracking is foreground tracking while the captain app is open; it is not guaranteed background tracking when the mobile OS suspends the browser/PWA.
- Public CARTO/OSRM/Nominatim endpoints are suitable for development and low-volume testing; use a production mapping provider or self-hosted services for sustained commercial traffic.
- Persistent media requires a persistent disk or external object storage; setting `MEDIA_ROOT` alone does not create the disk.
