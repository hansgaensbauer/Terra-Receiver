Getting Started
===============

This page describes the process of setting up a client device. 

``run_terra_client`` is the main entry point for client receivers. It can be run with arguments
from a command line, but works best with a setup contained in a ``.env`` file which is loaded
with ``dotenv``.

Obtaining Credentials
---------------------
We are currently beta testing. If you were provided with an access token, you can use it to 
obtain credentials for the backend:

.. raw:: html

    <form id="signup-form">
      <label for="invite_code">Invite Code:</label>
      <input type="text" id="invite_code" name="invite_code" required>
      <button type="submit">Sign Up</button>
    </form>

    <pre id="signup-output"></pre>

    <script>
      document.getElementById("signup-form").addEventListener("submit", function(e) {
        e.preventDefault();
        var inviteCode = document.getElementById("invite_code").value;
        var output = document.getElementById("signup-output");
        output.textContent = "Loading...";

        fetch("https://ajtaaxxrmj.execute-api.us-east-1.amazonaws.com/dev/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ invite_code: inviteCode })
        })
        .then(function(response) {
          return response.json().then(function(data) {
            return { status: response.status, body: data };
          });
        })
        .then(function(result) {
          output.textContent = "Status: " + result.status + "\n" + JSON.stringify(result.body, null, 2);
        })
        .catch(function(error) {
          output.textContent = "Error: " + error;
        });
      });
    </script>

Radio Configuration
-------------------
Terra is designed to work with a variety of software defined radios. Several drivers are provided 
for the most popular vendors, and adding new drivers is straightforward. To specify your radio setup,
create a ``.json`` file in ``Receiver/config/sources`` with structure like this:

.. code-block:: json

    {
        "driver":"soapy",
        "fs":6000000,
        "fc":94900000,
        "chunk_length":7200000,
        "source_kwargs":{
            "device_string":"driver=lime",
            "antenna":"LNAW",
            "gains":{
                "LNA":13,
                "TIA":9,
                "PGA":-6
            }
        }
    }

The parameters are:

:driver: 'soapy', 'uhd', or 'iio' are provided by default.
:fs: Sample rate in Hz
:fc: Center frequency in Hz. This will depend on the stations (see the following section)
:chunk_length: The computer-side buffer size for RF data.
:source_kwargs: Keyword arguments to be passed to the radio constructor. These will depend on the radio.

Environment Setup
-----------------
We highly recommend using a .env file to configure the receiver. A good starting point contains the following:

.. code-block:: bash

    CLIENT_GEOHASH=drt2
    DATASOURCE_FILE=config/sources/[your-radio-json-file]
    SERVER_URL=https://ajtaaxxrmj.execute-api.us-east-1.amazonaws.com/dev
    FEATURE_CLIENT_ID=[your-client-id]
    FEATURE_CLIENT_SECRET=[your-client-secret]
    COGNITO_DOMAIN='https://us-east-1cssiwx7hl.auth.us-east-1.amazoncognito.com'

CLIENT-GEOHASH is required to identify the region for which stations should be provided, we recommend a 4-character 
geohash for the receiver region.

Software defined radios are notoriously tricky to set up. We highly recommend `radioconda`_. Install radioconda, then
create a new python virtual environment using the python version in the radioconda install directory and use system site
packages, eg: ``~/radioconda/bin/python3 -m venv .venv --system-site-packages``. This will use the radioconda versions of 
SDR libraries like iio and uhd, but keep your radioconda installation clean. 

.. _radioconda: https://github.com/radioconda/radioconda-installer

Check that you can import the SDR libraries you need, then ``pip install -r requirements.txt``.

Starting the Receiver
---------------------
``python run_terra_client.py`` That should be it!

Web Interface
-------------
We have provided a `leaflet`_-based map/web interface for viewing solutions and the receiver location.

.. _leaflet: https://leafletjs.com/