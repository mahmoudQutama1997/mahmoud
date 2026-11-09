# WASELNI — Stage 1 Customer Storefront

## Delivered in this stage
- Added a typed React customer storefront in `frontend/src/customer/CustomerStorefront.tsx`.
- Added TypeScript configuration and Tailwind CSS v4 Vite integration.
- Customer home now loads the storefront and products from the existing authenticated Django endpoints (`GET /api/merchants/`, `GET /api/products/?merchant=<id>`).
- Cart supports multiple products from one merchant, quantity updates, removal, clear-cart, and persistence in browser local storage.
- Checkout creates a real cash-on-delivery store order through `POST /api/orders/` and sends an `Idempotency-Key` header.
- Customer can view recent orders returned by the existing API.
- Arabic-first layout with English and Hebrew translations; RTL for Arabic and Hebrew.
- Responsive purple visual system.
- No simulated online payment and no fabricated GPS data.

## Existing backend limitations retained transparently
- The current backend serializer accepts store orders only. Parcel requests are explicitly not enabled in this release; ride booking remains on the existing `/ride` screen and API action.
- Online payment is not integrated. Checkout only offers cash on delivery.
- Delivery pricing is not configured in the current backend; the storefront warns that the displayed amount is product subtotal only.
- Store listing and product endpoints require an authenticated user, consistent with the existing backend permissions.

## Install and run
From `frontend/`:

```bash
npm install
npm run dev
```

The project now declares these development dependencies: TypeScript, React type definitions, Tailwind CSS v4, and `@tailwindcss/vite`.

Run a production build with:

```bash
npm run build
```

From `backend/`, install `requirements.txt`, configure `.env`, then run migrations and the Django development server as documented in `README.md`.

## Verification status
Source integration and API contracts were inspected against the supplied Django project. A full frontend production build and Django system check could not be run in this execution environment because npm package installation timed out (registry access unavailable) and Django is not installed in the execution environment. Run the commands above in the project environment before deployment.
