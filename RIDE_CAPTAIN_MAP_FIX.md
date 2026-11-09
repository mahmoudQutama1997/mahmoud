# Captain ride route map fix

Assigned motorcycle rides now render an interactive Leaflet map inside the captain's order card.

- Reads the pickup/dropoff coordinates already stored on the Order record and returned by `OrderSerializer`.
- Displays distinct green pickup and red destination markers.
- Requests the road route from the public OSRM routing endpoint and draws the returned road geometry.
- Fits the map to the complete route and shows a legend/status.
- If road routing is unavailable, displays a dashed straight-line fallback and labels it as approximate.
- If coordinates are missing, shows a clear data warning instead of a blank map.

The existing customer ride form, order creation endpoint, database schema, and assignment flow are unchanged. The map uses the Leaflet CDN already loaded by `frontend/index.html`.

Note: the road geometry requires internet access to the public OSRM demo routing service and OpenStreetMap tiles. For production traffic, configure a dedicated routing provider/service.
