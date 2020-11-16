import inspect
from types import ModuleType
from typing import Dict, Callable

from sanic.websocket import WebSocketConnection

from match_pattern import Pattern
from zcommon.fs import relative_abspath
from zcommon.modules import try_load_module_dynamic_with_timestamp
from zcommon.textops import json_dump_with_types
from zcommon.collections import SerializableDict
from zthreading.events import AsyncEventHandler

from filebase_api.config import (
    FILEBASE_API_CORE_ROUTES_MARKER,
    FILEBASE_API_WEBSOCKET_MARKER,
    FILEBASE_API_REMOTE_METHODS_COLLECTION_MARKER,
    FILEBASE_API_PAGE_TYPE_MARKER,
    FILEBASE_API_REMOTE_METHOD_MARKER_ATTRIB_NAME,
    FILEBASE_API_REMOTE_METHOD_MARKER_CONFIG_ATTRIB_NAME,
    FilebaseApiRemoteMethodConfig,
)


class FilebaseApiCoreRoutes(SerializableDict):
    def __init__(self):
        super().__init__()
        self.load_core_object("filebase_api_client.js")

    def load_core_object(self, src):
        fullpath = relative_abspath(src)
        with open(fullpath, "r") as raw:
            self[src] = Pattern.format(
                raw.read(),
                custom_start_pattern="{!%",
                custom_end_pattern="%!}",
                FILEBASE_API_CORE_ROUTES_MARKER=FILEBASE_API_CORE_ROUTES_MARKER,
                FILEBASE_API_WEBSOCKET_MARKER=FILEBASE_API_WEBSOCKET_MARKER,
                FILEBASE_API_REMOTE_METHODS_COLLECTION_MARKER=FILEBASE_API_REMOTE_METHODS_COLLECTION_MARKER,
                FILEBASE_API_PAGE_TYPE_MARKER=FILEBASE_API_PAGE_TYPE_MARKER,
            )


class FilebaseApiWebSocket(AsyncEventHandler):
    def __init__(self, websocket: WebSocketConnection, on_event=None):
        super().__init__(on_event=on_event)
        self.websocket = websocket
        self.register_handler_events = True

    async def send(self, messge, as_json=False):
        if self.websocket.closed is True:
            return
        if as_json:
            messge = json_dump_with_types(messge)
        try:
            await self.websocket.send(str(messge))
        except Exception:
            pass

    async def send_event(self, name: str, *args, **kwargs):
        await self.send({"__event_name": name, "args": args, "dis": kwargs}, True)


class FilebaseApiModuleInfo:
    def __init__(self, module: ModuleType):
        super().__init__()

        # The associated code module.
        self._module = module
        self._websocket_command_functions: dict = None
        self._websocket_javascript_command_functions: dict = None

    @property
    def module(self) -> ModuleType:
        return self._module

    @property
    def websocket_command_functions(self) -> Dict[str, Callable]:
        """A collection of command functions to be exposed."""
        if self._websocket_command_functions is None:
            self._websocket_command_functions = dict()

            for cmnd_name in dir(self.module):
                cmnd = self.get_module_command_handler(cmnd_name)
                if cmnd is not None:
                    self._websocket_command_functions[cmnd_name] = cmnd

        return self._websocket_command_functions

    @property
    def websocket_javascript_command_functions(self) -> Dict[str, str]:
        """A collection of javascript functions to be printed on the client page javascript"""

        if self._websocket_javascript_command_functions is None:
            self._websocket_javascript_command_functions = dict()
            for name in self.websocket_command_functions.keys():
                if name.startswith("on_"):
                    continue
                config = self.get_module_command_handler_config(name) or FilebaseApiRemoteMethodConfig()
                if not config.expose_js_method:
                    continue
                signature = inspect.signature(self.websocket_command_functions[name])
                args = []
                input_args = []
                for arg_name in list(signature.parameters.keys())[1:]:
                    if signature.parameters[arg_name].default != inspect._empty:
                        input_args.append(arg_name + "=null")
                    else:
                        input_args.append(arg_name)
                    args.append(arg_name)
                js_code = f"""
async function fapi_{name}({','.join(input_args)}) {{
    return (await filebase_api.exec({{
        {name}:[{','.join(args)}]
    }})).{name}
}}
"""
                self._websocket_javascript_command_functions[name] = js_code.strip()

        return self._websocket_javascript_command_functions

    def get_module_command_handler(self, name: str) -> Callable:
        """Returns a command handler for the module by the name.

        Args:
            name (str): The command name

        Returns:
            Callable: The callable function. (page, ...)
        """
        if self.module is None:
            return
        cmnd = getattr(self.module, name, None)
        if cmnd is None or not (callable(cmnd) and hasattr(cmnd, FILEBASE_API_REMOTE_METHOD_MARKER_ATTRIB_NAME)):
            return None
        return cmnd

    def get_module_command_handler_config(self, name: str):
        """Returns the config of the command handler for the module by the name.

        Args:
            name (str): The command name
        """
        handler = self.get_module_command_handler(name)
        if handler is None or not hasattr(handler, FILEBASE_API_REMOTE_METHOD_MARKER_CONFIG_ATTRIB_NAME):
            return None

        return getattr(handler, FILEBASE_API_REMOTE_METHOD_MARKER_CONFIG_ATTRIB_NAME)

    @classmethod
    def load_from_path(cls, module_path: str) -> "FilebaseApiModuleInfo":
        """Loads a module from a module path.

        Returns:
            FilebaseApiModuleInfo
        """
        module = try_load_module_dynamic_with_timestamp(module_path)
        if module is None:
            return None

        if not hasattr(module, "__filebase_api_module_info"):
            # thread blocking command
            module.__filebase_api_module_info = cls(module)

        return module.__filebase_api_module_info
