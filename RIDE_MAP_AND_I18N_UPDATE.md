# WASELNI update — ride maps and location language

Date: 2026-11-06

## Changes applied to the supplied project

- Reused the existing `RideRouteMap` component in the customer's **My Rides** list as well as the captain's assigned-ride view.
- The shared map shows pickup and destination markers, requests OSRM road geometry, fits the map to the route, and shows OSRM distance and estimated duration when a road route is returned.
- If OSRM fails, the map shows a dashed approximate straight line and an explicit approximate-route label. Missing coordinates show a translated warning.
- Localized map headings, route states, pickup/destination labels, distance and duration for Arabic, English and Hebrew.
- Replaced the hard-coded Arabic strings in the ride-booking form with dictionary keys for the three supported languages.
- Added reverse geocoding for map selections and current-location selections through a configurable Nominatim-compatible endpoint. Users can still edit the place name manually.
- Added editable latitude/longitude inputs for pickup and destination. Valid manual coordinate changes update the corresponding map markers; clearing coordinates removes the marker.
- Added configurable frontend environment variables:
  - `VITE_OSRM_URL`
  - `VITE_GEOCODING_URL`

## Important limitations retained and disclosed

- The backend ride fare is still calculated from a straight-line Haversine estimate with a margin. It is **not** calculated from the OSRM road distance. The UI displays road distance/duration on the map but does not present them as the fare basis.
- The default OSRM and Nominatim URLs are public demonstration/community services. They have usage policies and no production availability guarantee. Configure dedicated services for production traffic.
- Reverse geocoding is best-effort. If the service is unavailable or does not return a name, the user can enter the address manually.
- This update does not claim to complete every item in the supplied master prompt. Other areas (including full system-wide translation cleanup, admin/store workflow audit, production notification providers, payments, live GPS, and full end-to-end QA) still require additional implementation and environment-specific verification.

## Verification performed in this environment

- Backend Python source compilation: passed.
- Frontend JSX/JavaScript syntax transpilation check using the installed TypeScript parser: passed.
- CSS brace-balance check: passed.
- Arabic/English/Hebrew translation-key parity: passed.
- Django runtime checks and API tests: not run; Django is not installed in this environment.
- Vite production build: not run; `frontend/node_modules` is not installed.

## Local verification commands

Backend (inside `backend/` after installing requirements):

```bash
python manage.py check
python manage.py makemigrations --check
python manage.py test
```

Frontend (inside `frontend/`):

```bash
npm install
npm run build
```

## Startup

Follow the existing `README.md` instructions. Copy `frontend/.env.example` to `.env` and adjust the API, OSRM and geocoding endpoints as needed. Keep Django and Vite running in separate terminals during local development.
