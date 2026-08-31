import time
from threading import RLock

import requests


class CowboyAPIClient:
    def __init__(self, bike_id=None) -> None:
        self.email = None
        self.password = None
        self.base_url = "https://app-api.cowboy.bike"
        self.app_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        self.client_type = "HomeAssistant-App"
        self.access_token = None
        self.uid = None
        self.client = None
        self.token_expires = None
        self._request_lock = RLock()
        # Snapshot of the fields above, rebound as a whole whenever they
        # change so export_session() can read it without taking the lock --
        # a request may hold the lock for the full 30s timeout, and this is
        # read from the event loop.
        self._session = None

        # When bike_id is provided, all per-bike endpoints use it regardless of
        # which bike happens to be active in the login response. When it's
        # None (initial config flow), login() backfills it from data.bike.id.
        self.bike_id = bike_id

    def login(self, email, password):
        with self._request_lock:
            self.email = email
            self.password = password
            url = f"{self.base_url}/auth/sign_in"
            headers = {
                "content-type": "application/json",
                "X-Cowboy-App-Token": self.app_token,
                "Client-Type": self.client_type,
            }
            payload = {"email": email, "password": password}
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            self._update_session(response)

            json_response = response.json()

            if self.bike_id is None:
                self.bike_id = json_response["data"]["bike"]["id"]

            return json_response

    def _update_session(self, response):
        """Update authentication details returned by the API."""
        if access_token := response.headers.get("Access-Token"):
            self.access_token = access_token
        if uid := response.headers.get("Uid"):
            self.uid = uid
        if client := response.headers.get("Client"):
            self.client = client
        if expiry := response.headers.get("Expiry"):
            self.token_expires = int(expiry)
        self._snapshot_session()

    def _snapshot_session(self):
        """Rebind the exportable session snapshot."""
        if not self.access_token or not self.uid or not self.client:
            self._session = None
            return
        self._session = {
            "access_token": self.access_token,
            "uid": self.uid,
            "client": self.client,
            "token_expires": self.token_expires,
        }

    def export_session(self):
        """Return the current session, or None when not signed in.

        Safe to call from the event loop: it reads a single attribute that is
        rebound as a whole, so it never blocks on the request lock.
        """
        return self._session

    def restore_session(self, email, password, session):
        """Reuse a stored session instead of signing in again.

        Credentials are still needed: the client falls back to signing in when
        the session turns out to be expired or rejected.
        """
        with self._request_lock:
            self.email = email
            self.password = password
            self.access_token = session.get("access_token")
            self.uid = session.get("uid")
            self.client = session.get("client")
            self.token_expires = session.get("token_expires")
            self._snapshot_session()

    def _auth_headers(self):
        """Return authentication headers for an API request."""
        return {
            "content-type": "application/json",
            "X-Cowboy-App-Token": self.app_token,
            "Access-Token": self.access_token,
            "Client-Type": self.client_type,
            "Uid": self.uid,
            "Client": self.client,
        }

    def _is_token_expired(self):
        if self.token_expires is None:
            return False
        current_time = int(time.time())
        return current_time >= self.token_expires

    def _renew_token(self):
        self.login(self.email, self.password)

    def logout(self):
        with self._request_lock:
            if not self.access_token or not self.uid or not self.client:
                raise ValueError("Not logged in")
            url = f"{self.base_url}/auth/sign_out"
            response = requests.delete(url, headers=self._auth_headers(), timeout=5)
            response.raise_for_status()
            return response.json()

    def get_user_info(self):
        return self._get_endpoint("/users/me")

    def get_user_badges(self):
        return self._get_endpoint("/users/me/badges")

    def get_user_badges_recent(self):
        return self._get_endpoint("/users/me/badges/recent")

    def get_user_records(self):
        return self._get_endpoint("/users/me/personal_records")

    def get_user_places(self):
        return self._get_endpoint("/users/me/places")

    def get_user_smart_companions(self):
        return self._get_endpoint("/users/me/smart_companions")

    def get_bike(self):
        return self._get_endpoint(f"/bikes/{self.bike_id}")

    def get_bike_nicknames(self):
        return self._get_endpoint("/bikes/nicknames")

    def get_trips_offset(self):
        return self._get_endpoint("/trips/offset")

    def get_trips_recent(self):
        return self._get_endpoint("/trips/recent")

    def get_trips_metrics(self):
        return self._get_endpoint("/trips/metrics/stats")

    def get_trips_highlights(self):
        return self._get_endpoint("/trips/highlights")

    def get_diagnostics_help(self):
        return self._get_endpoint("/diagnostics/help")

    def get_dfcs_offset(self):
        return self._get_endpoint("/dfcs/offset")

    def get_releases(self):
        return self._get_endpoint("/releases")

    def get_crashes_current(self):
        return self._get_endpoint("/crashes/current")

    def get_theft(self):
        return self._get_endpoint("/theft")

    def _get_endpoint(self, endpoint, timeout=30):
        with self._request_lock:
            if not self.access_token or not self.uid or not self.client:
                raise ValueError("Not logged in")
            if self._is_token_expired():
                self._renew_token()

            url = f"{self.base_url}{endpoint}"
            response = requests.get(
                url, headers=self._auth_headers(), timeout=timeout
            )

            if response.status_code == 401:
                self._renew_token()
                response = requests.get(
                    url, headers=self._auth_headers(), timeout=timeout
                )

            response.raise_for_status()
            self._update_session(response)
            return response.json()
