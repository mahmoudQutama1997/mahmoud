# Duplicate order submission fix

- Customer order and ride forms now lock synchronously while a submission is in progress, so rapid repeated clicks cannot trigger multiple requests.
- Each intentional submission receives an `Idempotency-Key`.
- The backend stores that key per customer and returns the original order if the same request is retried, without publishing a second `order.created` event.
- After a successful store order, the product and delivery address fields are cleared. After a successful ride request, pickup/destination fields and map markers are cleared so a new ride requires selecting new locations.
- A customer can still create another order or ride after completing the next form; there is no rule limiting customers to one order.
- Existing order records are not deleted or merged. Any duplicate orders already present remain unchanged.

## Apply the database migration

From the `backend` directory, activate the project's virtual environment and run:

```bash
python manage.py migrate
```

This applies `core.0007_order_idempotency_key`, adding a nullable idempotency key and a per-customer uniqueness constraint. It does not reset or delete the database.

## Verification

Python syntax compilation passed for the changed backend modules and migration. Django tests and the React production build were not run because Django/frontend dependencies are not installed in this environment.
