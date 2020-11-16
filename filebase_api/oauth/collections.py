from datetime import datetime, timedelta
from zcommon.collections import SerializableDict


class FilebaseApiOAuthDeviceAuthResponse(SerializableDict):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if "created_at" not in self:
            self["created_at"] = datetime.now().isoformat()

    @property
    def created_at(self) -> datetime:
        as_iso = self.get("created_at", None)
        if as_iso is None:
            return None
        return datetime.fromisoformat(as_iso)

    @property
    def verification_uri(self) -> str:
        return self.get("verification_uri", None)

    @property
    def device_code(self) -> str:
        return self.get("device_code", None)

    @property
    def user_code(self) -> str:
        return self.get("user_code", None)

    @property
    def expires_in(self) -> timedelta:
        expires_in_seconds = float(self.get("expires_in", None))
        if expires_in_seconds is None:
            return None
        return timedelta(seconds=expires_in_seconds)

    @property
    def interval(self) -> timedelta:
        interval_seconds = float(self.get("interval", None))
        if interval_seconds is None:
            return None
        return timedelta(seconds=interval_seconds)

    @property
    def remaining_experation_time(self) -> timedelta:
        return self.expires_in - (datetime.now() - self.created_at)

    @property
    def is_expired(self) -> bool:
        return self.remaining_experation_time.total_seconds() < 0

    @property
    def remaining_interval_time(self) -> timedelta:
        return self.interval - (datetime.now() - self.created_at)

    @property
    def is_interval_ready(self) -> bool:
        return self.remaining_interval_time.total_seconds() < 0


class FilbeaseApiOAuthClientConfig(SerializableDict):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    @property
    def scope(self) -> str:
        return self.get("scope", None)

    @scope.setter
    def scope(self, val: str):
        self["scope"] = val

    @property
    def client_id(self) -> str:
        return self.get("client_id", None)

    @client_id.setter
    def client_id(self, val: str):
        self["client_id"] = val

    @property
    def client_secret(self) -> str:
        return self.get("client_secret", None)

    @client_secret.setter
    def client_secret(self, val: str):
        self["client_secret"] = val

    @property
    def name(self) -> str:
        return self.get("name", None)

    @name.setter
    def name(self, val: str):
        self["name"] = val

    @property
    def base_url(self) -> str:
        """The api server base url."""
        return self.get("resource_server", None)

    @base_url.setter
    def base_url(self, val: str):
        self["resource_server"] = val

    @property
    def authorize_server_url(self) -> str:
        return self.get("authorize_server_url", self.base_url)

    @authorize_server_url.setter
    def authorize_server_url(self, val: str):
        self["authorize_server_url"] = val

    @property
    def token_server_url(self) -> str:
        return self.get("token_server_url", self.base_url)

    @token_server_url.setter
    def token_server_url(self, val: str):
        self["token_server_url"] = val

    @property
    def extra_args(self) -> dict:
        if "extra_args" not in self:
            self["extra_args"] = {}
        return self.get("extra_args", {})

    @extra_args.setter
    def extra_args(self, val: dict):
        self["extra_args"] = val

    @property
    def state_id_param_name(self) -> str:
        return self.get("state_id_param_name", "state")

    @state_id_param_name.setter
    def state_id_param_name(self, val: str):
        self["state_id_param_name"] = val
