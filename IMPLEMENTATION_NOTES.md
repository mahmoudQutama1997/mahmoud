# Waselni – Captain & Merchant Workflow Update

## Implemented in this update
- Captain registration accepts identity/permit, driving-license and insurance document uploads (PDF/JPG/PNG, max 10 MB each) and requires explicit digital-undertaking acceptance.
- Captain profile API exposes document-presence flags; captains can upload/replace their documents from their profile. Verification remains administrator-controlled.
- Admin captain approval endpoint can grant/revoke `checkpoint_badge` without changing the existing approval state. The existing centralized eligibility/checkpoint filter remains the source of truth for dispatch.
- Added `Order.merchant_arrived_at` and a captain-only `/api/orders/<id>/arrive/` action.
- Store-order pickup cannot be confirmed until the captain records arrival.
- Delay reports are accepted only for the assigned captain's store order and only after 10 free minutes from the recorded arrival. Duplicate reports are rejected.
- Cash settlement is automatically created once a cash store order is marked picked up. Merchant and captain must both confirm it; delivery cannot start until it is closed. Confirmation is transaction-locked and idempotent.
- Merchant order cards show preparation countdown and arrival time. Merchant and captain can access the shared settlement screen.
- Added `/api/merchant/reports/` for today's completed gross sales, order counts, and today's cash settlement ledger.
- Captain SOS control creates a support ticket containing a one-time location snapshot when geolocation is available.

## Migration
Run from `backend/`:

```bash
python manage.py migrate
```

Migration `0008_captain_documents_arrival` only adds nullable document/date fields. It does not delete or reset existing data.

## Important limitations / business rules still needed
- Net merchant earnings are intentionally not calculated because the platform commission/subscription deduction rule has not been specified. The report returns `net_sales_today: null` with an explanation instead of inventing a figure.
- Delay reports are recorded, but automatic merchant fines, captain waiting compensation, and reliability-score penalties are not posted because their amounts/formula and approval workflow are not specified. Do not treat a report as a posted financial charge.
- SOS currently records an authenticated support ticket and a location snapshot; it is not continuous live-location streaming or an emergency calling service.
- VoIP and masked in-app calling/chat require a telephony/messaging provider, credentials, and retention/privacy policy. No provider credentials were supplied, so no fake calling feature was added.
- Maps deep-links, real-time route guidance, and full navigation provider integration remain separate work.

## Checks
- Python compilation (`compileall`) passed.
- Django `manage.py check`, migrations check, Django tests, and Vite production build were not run because Django/frontend dependencies are not installed in this environment.
