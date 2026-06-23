API Documentation
=================

Overview
--------

This API provides access to station metadata and feature data
collected from reference receivers. Data is retained for a short
window (a few minutes) after collection.

All endpoints require authentication via OAuth2 client credentials issued
by Amazon Cognito. Clients must request an access token from the Cognito
token endpoint and include it as a bearer token on each request.

.. code-block:: text

   Authorization: Bearer <access_token>

Authentication
---------------

Access tokens are obtained via the OAuth2 client credentials grant:

.. code-block:: http

   POST /oauth2/token HTTP/1.1
   Host: <cognito-domain>
   Content-Type: application/x-www-form-urlencoded

   grant_type=client_credentials&client_id=<client_id>&client_secret=<client_secret>&scope=sensor-api/read

The response contains an ``access_token`` and ``expires_in`` (seconds).
Tokens should be cached and refreshed shortly before expiry.

Endpoints
---------

GET /stations
~~~~~~~~~~~~~~

Return all active stations within a 30 km radius of a point.

**Required scope:** ``sensor-api/read``

Query Parameters
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 10 75

   * - Name
     - Type
     - Description
   * - ``lat``
     - float
     - Latitude of the center point, in decimal degrees.
   * - ``lon``
     - float
     - Longitude of the center point, in decimal degrees.

Response
^^^^^^^^^

``200 OK`` with a JSON body:

.. code-block:: json

   {
     "stations": [
       {
         "station_id": "664e6117-676c-11f1-943c-0ba28edaa340",
         "callsign": "WWWW"
         "lat": 51.5074,
         "lon": -0.1278,
         "bandwidth": 400000,
         "frequency": 1000000000
       }
     ],
     "count": 1
   }

Only stations falling within the requested radius
are returned.

Example
^^^^^^^

.. code-block:: bash

   curl "https://<api-url>/stations?lat=51.5074&lon=-0.1278" \
        -H "Authorization: Bearer <access_token>"

GET /features
~~~~~~~~~~~~~~

Return time-series feature data for one or more stations within a given
time range.

**Required scope:** ``sensor-api/read``

If recent data is unavailable for a requested station, the corresponding
sensor is woken automatically; the station is omitted from the response
until data becomes available on a subsequent request.

Query Parameters
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 10 75

   * - Name
     - Type
     - Description
   * - ``station_ids``
     - string
     - Comma-separated list of station UUIDs.
   * - ``time_from``
     - integer
     - Start of the time range, as a Unix epoch timestamp in
       **nanoseconds**.
   * - ``time_to``
     - integer
     - End of the time range, as a Unix epoch timestamp in
       **nanoseconds**.

Response
^^^^^^^^^

``200 OK`` with a ``msgpack``-encoded body
(``Content-Type: application/msgpack``).

The decoded body is a mapping of station ID to a list of feature
records. Stations with no data in the requested range are omitted
entirely.

Each feature record has the following structure:

.. list-table::
   :header-rows: 1
   :widths: 15 10 75

   * - Field
     - Type
     - Description
   * - ``timestamp``
     - integer
     - Sample timestamp, Unix epoch nanoseconds.
   * - ``station_id``
     - string
     - UUID of the originating station.
   * - ``index``
     - integer
     - -1. For use within the receiver.
   * - ``real``
     - array[float]
     - Real components of the complex sample array.
   * - ``imag``
     - array[float]
     - Imaginary components of the complex sample array, in the same
       order as ``real``.

Example
^^^^^^^

.. code-block:: python

   import requests
   import msgpack

   response = requests.get(
       "https://<api-url>/features",
       params={
           "station_ids": "664e6117-676c-11f1-943c-0ba28edaa340",
           "time_from": 1781391384818170011,
           "time_to": 1781391388818170011,
       },
       headers={"Authorization": f"Bearer {access_token}"},
   )
   data = msgpack.unpackb(response.content, raw=False)

   for station_id, features in data.items():
       print(station_id, len(features))

POST /signup
~~~~~~~~~~~~~

Request a new set of client credentials for the ``sensor-api/read``
scope. Intended for issuing credentials to beta testers during a
limited signup window.

**Required scope:** none (gated by invite code instead)

.. note::

   This endpoint may be disabled at any time. A ``403`` response
   indicates that signups are currently closed.

Request Body
^^^^^^^^^^^^^

.. code-block:: json

   {
     "invite_code": "<invite_code>"
   }

Response
^^^^^^^^^

``200 OK``:

.. code-block:: json

   {
     "client_id": "...",
     "client_secret": "..."
   }

``401 Unauthorized`` if the invite code is invalid.

``403 Forbidden`` if signups are currently closed.

Data Retention
---------------

Feature data is retained for approximately five minutes after upload.
Queries for time ranges outside this window will return no data for
the affected stations.

Rate Limiting
--------------

All endpoints are subject to throttling at the API gateway level.
Exceeding the configured rate returns ``429 Too Many Requests``.