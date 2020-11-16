from uuid import uuid4
from datetime import timedelta
from typing import Union, Callable
from zthreading.events import EventHandler
from filebase_api.web import ClientRestRequest, Client
from filebase_api.oauth.collections import FilbeaseApiOAuthClientConfig


class FilbeaseApiOAuthClient(EventHandler):
    log_event_name = "log"

    def __init__(
        self,
        config: Union[FilbeaseApiOAuthClientConfig, dict] = None,
        state_id: str = None,
    ) -> None:
        self.config = config or FilbeaseApiOAuthClientConfig()
        if isinstance(self.config, dict):
            self.config = FilbeaseApiOAuthClientConfig(self.config)

        assert isinstance(self.config, FilbeaseApiOAuthClientConfig), ValueError(
            "Config must be a dictionary or FilbeaseApiOAuthClientConfig"
        )

        self.state_id = state_id or f"{uuid4()}"

    def authorize_device(
        self,
        check_device_token_ready: Callable = None,
        wait_interval: Union[timedelta, float] = timedelta(seconds=1),
        wait_interval_count: int = 3,
    ):
        pass
