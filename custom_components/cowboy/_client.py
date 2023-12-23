import time

import requests


class CowboyAPIClient:
    def __init__(self) -> None:
        self.password = None
        self.base_url = "https://app-api.cowboy.bike"
        self.app_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        self.client_type = "Android-App"
        self.access_token = None
        self.uid = None
        self.client = None
        self.token_expires = None

        self.bike_id = None
        self.model = None
        self.nickname = None
        self.serial_number = None

    def login(self, email, password):
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

        self.access_token = response.headers.get("Access-Token")
        self.uid = response.headers.get("Uid")
        self.client = response.headers.get("Client")
        self.token_expires = int(response.headers.get("Expiry"))

        json_response = response.json()

        # store some stuff that is returned by the login already;
        # coordinators use it to set up the device info. note that there
        # can only be a single bike per account (as it looks like in the
        # returned data), so we can just use this one here.

        self.bike_id = json_response["data"]["bike"]["id"]
        self.model = json_response["data"]["bike"]["model"]["name"]
        self.serial_number = json_response["data"]["bike"]["serial_number"]

        return json_response

    def _is_token_expired(self):
        current_time = int(time.time())
        return current_time >= self.token_expires

    def _renew_token(self):
        self.login(self.uid, self.password)

    def logout(self):
        if not self.access_token or not self.uid or not self.client:
            raise ValueError("Not logged in")
        url = f"{self.base_url}/auth/sign_out"
        headers = {
            "content-type": "application/json",
            "X-Cowboy-App-Token": self.app_token,
            "Access-Token": self.access_token,
            "Client-Type": self.client_type,
            "Uid": self.uid,
            "Client": self.client,
        }
        response = requests.delete(url, headers=headers, timeout=5)
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

    def get_bike_status(self):
        return self._get_endpoint(f"/bikes/{self.bike_id}/status")

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
        if not self.access_token or not self.uid or not self.client:
            raise ValueError("Not logged in")
        if self._is_token_expired():
            self._renew_token()
        url = f"{self.base_url}{endpoint}"
        headers = {
            "content-type": "application/json",
            "X-Cowboy-App-Token": self.app_token,
            "Access-Token": self.access_token,
            "Client-Type": self.client_type,
            "Uid": self.uid,
            "Client": self.client,
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
