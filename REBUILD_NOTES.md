# Waselni rebuild notes — In-app administration

This revision keeps Django as the API/database backend and moves operational administration into the React application.

## What changed
- Removed the Django Admin website route (`/admin/`). Platform operations are performed through the React app.
- Protected the React `/admin` route so only an authenticated `admin` role can open it.
- Added a dedicated in-app subscription ledger with account identity, role, subscription dates, status, paid amount, due amount, remaining balance, payment recording, and status updates.
- Centralized subscription evaluation in `subscription_state()` and reused it in captain self-status, admin account listing, admin operations, and dispatch eligibility.
- Added tests for subscription ledger status updates and for admin/captain reporting the same inactive state when a subscription is missing.
- Updated README setup instructions and API endpoint list.

## Important behavior
A subscription is active only when all three conditions are true:
- `status == active`
- `starts_on <= local date`
- `ends_on >= local date`

If a user has `subscription_required=True` and has no matching current subscription, the captain cannot go online or receive orders. The admin dashboard shows the same calculated state.

## Local startup
Backend: create/activate a virtual environment, install `backend/requirements.txt`, run migrations, and create the initial platform administrator with `python manage.py createsuperuser`.
Frontend: run `npm install` and `npm run dev`.
Sign in through the React app. The platform administrator is redirected to the in-app dashboard at `/admin`.

## Verification limits
Python source compilation and JavaScript utility-file syntax checks were completed. Full Django tests and Vite production build were not run in this environment because Django/frontend packages are not installed and package network access is unavailable. Run the test/build commands locally after installing dependencies.
