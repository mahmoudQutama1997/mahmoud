# Waselni – Store and Delivery Location Maps

## Implemented

- Merchant store profile now includes an interactive Leaflet/OpenStreetMap location picker, address search, browser GPS, draggable marker, and saved latitude/longitude.
- Merchant profile API now reads/writes store coordinates and validates coordinate ranges and paired values.
- Public merchant records expose the saved coordinates so the customer can see the store pin while choosing a delivery location.
- Customer checkout now requires selecting a delivery point on the map, supports address search/GPS/marker movement, stores delivery coordinates and extra delivery notes with the order, and shows the selected store point when available.
- Store orders automatically copy the merchant's saved address and coordinates into the order pickup fields.
- Admin overview map displays geolocated stores and active order pickup/delivery points, with popups and a connecting line for orders that have both points.
- Admin store and operations APIs now return coordinates needed by the map.
- Added `Order.dropoff_notes` with a non-destructive Django migration.
- Map controls include Arabic, English, and Hebrew labels.

## Apply the database migration

From `backend`:

```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

From `frontend` in a second terminal:

```bash
npm install
npm run dev
```

## How to use

1. Sign in as a merchant and open **Profile / Store Profile**.
2. Enter the store address, choose the exact store point on the map (or use GPS/search), and save the profile.
3. Sign in as admin and open the dashboard overview. The store marker appears after the admin data refresh.
4. Sign in as a customer, choose an available store and product, enter/confirm the delivery address, choose the delivery point on the map, and submit the order.
5. Admin sees the store pickup and customer delivery points for active orders.

## Important notes

- Map tiles and address search use OpenStreetMap/Leaflet and Nominatim public endpoints; they require internet access. Public endpoints have usage policies and are suitable for development/testing, not guaranteed high-volume production infrastructure.
- Browser GPS requires permission and a secure context (localhost is allowed; deployed sites should use HTTPS).
- Existing stores without coordinates remain in the database and in the admin store list; they will not have a map marker until the merchant saves a location.
- Customer store visibility rules were intentionally preserved: a store must be open and satisfy the existing subscription-access rule. The map work does not bypass merchant approval/subscription controls.
- Existing orders keep their existing data; new store orders copy the merchant pickup point when it has been saved.

## Validation performed

- Python source compilation: passed (`python -m compileall -q backend`).
- TypeScript compiler JSX/JavaScript parse check: passed (`tsc --allowJs --checkJs false --jsx react --noEmit --noResolve --target ES2022 --module ESNext frontend/src/App.jsx`).
- Django `manage.py check` and test suite could not run because Django is not installed in this build environment.
- Vite production build could not run because frontend dependencies were not installed; `npm install` timed out in this environment. Run the commands above locally to complete runtime verification.
