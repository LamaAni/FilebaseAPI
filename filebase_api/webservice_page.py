import ujson
import traceback

from typing import Dict, Callable, Type
from enum import Enum

from sanic.request import Request
from sanic_session.base import BaseSessionInterface, SessionDict, get_request_container
from sanic_oauth.providers import OAuth2Client

from zcommon.shell import logger
from zcommon.textops import create_unique_string_id
from zthreading.events import AsyncEventHandler
from zthreading.decorators import collect_consecutive_calls_async
from zthreading.tasks import wait_for_future

from filebase_api.config import FilebaseApiConfig
from filebase_api.helpers import FilebaseApiModuleInfo, FilebaseApiWebSocket


class FilebaseApiPage(AsyncEventHandler, dict):
    __inproc_cache: Dict[str, "FilebaseApiPage"] = dict()
    expose_client_js_bindings: bool = True

    def __init__(
        self,
        api: "FilebaseApi",  # noqa: F821
        sub_path: str,
        module_info: FilebaseApiModuleInfo,
        request: Request,
        page_id: str = None,
    ):
        """A page object, associate with the current executing websocket or page render.

        Args:
            api (FilebaseApi): The filebase api.
            module_info (FilebaseApiModuleInfo): The associated module (code)
            request (Request): The sanic request.
            page_id (str, optional): The page id. Defaults to None.
        """
        super().__init__(on_event=None)
        self._page_id = page_id or f"{sub_path}-{create_unique_string_id()}"
        self._api = api
        self._request = request
        self._sub_path = sub_path
        self._ws: FilebaseApiWebSocket = None
        self._bind_events = dict()
        self._ws_command_functions = None
        self._module_info = module_info

        self._configure_session_autosave()

    def __hash__(self):
        return self.page_id.__hash__()

    @property
    def page_id(self) -> str:
        """The page id"""
        return self._page_id

    @property
    def request(self) -> Request:
        """The sanic request"""
        return self._request

    @property
    def api(self) -> "FilebaseApi":  # noqa: F821
        """The assciated filebase api."""
        return self._api

    @property
    def api_config(self) -> FilebaseApiConfig:
        return self.api.config

    @property
    def session_interface(self) -> BaseSessionInterface:
        return self.api.session_interface

    @property
    def sub_path(self) -> str:
        """The public route subpath (if any)"""
        return self._sub_path

    @property
    def websocket(self) -> FilebaseApiWebSocket:
        """The associated websocket if this is a websocket call (if any)"""
        return self._ws

    @property
    def is_websocket_state(self) -> bool:
        """True if this is a websocket call."""
        return self.websocket is not None

    @property
    def module_info(self) -> FilebaseApiModuleInfo:
        """The code module information and value."""
        return self._module_info

    @property
    def has_code_module(self) -> bool:
        """If true has a code module."""
        return self.module_info is not None

    @property
    def websocket_command_functions(self) -> Dict[str, Callable]:
        """The associated list of all command functons in the code module."""
        return self.module_info.websocket_command_functions

    @property
    def websocket_javascript_command_functions(self) -> Dict[str, str]:
        """The associated collection of client side js
        functions that match the command functions
        """
        return self.module_info.websocket_javascript_command_functions

    @property
    def session(self) -> SessionDict:
        return get_request_container(self.request)[self.session_interface.session_name]

    @property
    def oauth_token(self) -> str:
        return self.session.get("token", None)

    @property
    def oauth_provider(self) -> str:
        return self.session.get("oauth_provider", None)

    @property
    def oauth_user_info(self) -> dict:
        return self.session["oauth_user_info"]

    @oauth_user_info.setter
    def oauth_user_info(self, val: dict):
        self.session["oauth_user_info"] = val

    @oauth_provider.setter
    def oauth_provider(self, val: str):
        self.session["oauth_provider"] = val

    @collect_consecutive_calls_async(on_error="_save_session_async_error")
    def _save_session_async(self):
        # ignore the response dict (i.e. the cookie)
        req = get_request_container(self.request)
        val = ujson.dumps(dict(req[self.session_interface.session_name]))
        key = self.session_interface.prefix + req[self.session_interface.session_name].sid
        wait_for_future(self.session_interface._set_value(key, val))

    def _save_session_async_error(self, err):
        logger.error(traceback.format_exception(err))
        logger.error("Failed to save session.")

    def _configure_session_autosave(self):
        if (
            hasattr(self.session, "_filebase_api_session_autosave_enabled")
            and self.session._filebase_api_session_autosave_enabled is True
        ):
            return

        self.session._filebase_api_session_autosave_enabled = True

        call_session_dict_on_update = self.session.on_update

        def call_on_update(*args, **kwargs):
            if callable(call_session_dict_on_update):
                call_session_dict_on_update(*args, **kwargs)
            self._save_session_async()

        self.session.on_update = call_on_update

        # override the set attribute.
        self.session.__setattr__ = set

    def register_event_if_exists(self, name: str, event_handler: AsyncEventHandler):
        """Registers a new event for the command handlers in the modules, if the handler exists.

        Args:
            name (str): the event name (load,) ....
            event_handler (AsyncEventHandler): The event handler.
        """
        handler = self.module_info.get_module_command_handler("on_" + name)
        if handler is None:
            return
        event_handler.on(name, handler)

    def bind_event(self, name: str, skip_args_list: bool = False):
        """Binds events between client and server. An event on the server will
        be triggered also on the client (webpage)

        Args:
            name (str): the event to bind.
            skip_args_list (bool, optional): If true event arguments are not passed. Defaults to False.
        """
        assert self.is_websocket_state, Exception("Cannot bind events in non websocket state. See is_websocket_state")

        if isinstance(name, Enum):
            name = str(name)

        assert isinstance(name, str), ValueError("The event name must be a string or enum.")

        self._bind_events[name] = skip_args_list

    def clear_bound_event(self, name: str):
        """Removes a bound event. see bind_events"""
        assert self.is_websocket_state, Exception("Cannot bind events in non websocket state. See is_websocket_state")

        if isinstance(name, Enum):
            name = str(name)

        assert isinstance(name, str), ValueError("The event name must be a string or enum.")

        if name in self._bind_events:
            del self._bind_events[name]

    async def emit(self, name: str, *args, **kwargs):
        """Emmits a new event, bound events are also transmitted to the client (browser js).

        Args:
            name (str): The event name
        """
        rt_value = await super().emit(name, *args, **kwargs)
        if self.websocket is not None and name in self._bind_events:
            if self._bind_events[name]:
                args = []
                kwargs = {}
            await self.websocket.send_event(name, *args, **kwargs)
        return rt_value

    def oauth_client_from_provider(self, provider: str) -> OAuth2Client:
        provider = provider or self.oauth_provider
        assert provider in self.api_config.oauth_clients, Exception(f"OAuth provider client type {provider} not found")
        client_class: Type[OAuth2Client] = self.api_config.oauth_clients[provider]
        if isinstance(client_class, str):
            parts = client_class.split(".")
            mod = __import__(".".join(parts[:-1]))
            client_class = getattr(mod, parts[-1])

        assert issubclass(client_class, OAuth2Client), Exception(f"Invalid oauth client type: {type(client_class)}")

        return client_class(token=self.oauth_token)

    async def oauth_load(self, provider: str = None) -> bool:
        if self.oauth_token is None:
            return False

        if self.oauth_user_info is not None:
            return True

        client: OAuth2Client = self.oauth_client_from_provider(provider=provider)
        user_info = (await client.user_info()).__dict__
        for k in list(user_info.keys()):
            if k.startswith("_"):
                del user_info[k]

        self.oauth_user_info = user_info
        return True
