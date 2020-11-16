import os
from typing import List, Dict, Type

from sanic_oauth.providers import (
    GithubClient,
    GitlabClient,
    AmazonClient,
    GoogleClient,
    Bitbucket2Client,
    DiscordClient,
    OAuth2Client,
)

from match_pattern import Pattern
from zcommon.fs import load_config_files_from_path
from zcommon.collections import SerializableDict

# from zthreading.decorators import collect_delayed_calls_async

FILEBASE_API_REMOTE_METHOD_MARKER_ATTRIB_NAME = "__filebase_api_remote_method"
FILEBASE_API_REMOTE_METHOD_MARKER_CONFIG_ATTRIB_NAME = FILEBASE_API_REMOTE_METHOD_MARKER_ATTRIB_NAME + "_config"
FILEBASE_API_WEBSOCKET_MARKER = "__filebase_api_websocket"
FILEBASE_API_CORE_ROUTES_MARKER = "__filebase_api_core"
FILEBASE_API_REMOTE_METHODS_COLLECTION_MARKER = "__filebase_api_websocket_methods.js"
FILEBASE_API_PAGE_TYPE_MARKER = "__filebase_pt"
FILEBASE_API_CORE_PAGES_MARKER = "__filebase_api_pages"

FILEBASE_API_CORE_PAGES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pages")

FILEBASE_API_OAUTH_DEFAULT_PROVIDERS: Dict[str, Type[OAuth2Client]] = {
    "google": GoogleClient,
    "amazon": AmazonClient,
    "github": GithubClient,
    "gitlab": GitlabClient,
    "bitbucket": Bitbucket2Client,
    "discord": DiscordClient,
}


class FilebaseTemplateServiceConfig(SerializableDict):
    def __init__(self, **kwargs):
        super().__init__()
        self.update(kwargs)

    def load_from_path(self, src_path: str, pattern: Pattern = None):
        """Loads a configuration from path into the current object."""
        self.update(load_config_files_from_path(src_path, pattern or "filebase.yaml|filebase.yml|filebase.json"))

    @classmethod
    def load_config_from_path(cls, src_path: str, pattern: Pattern = None, **kwargs):
        """Loads the configuration from a path and creates a new config object."""
        val = cls(**kwargs)
        val.load_config_from_path(src_path, pattern)
        return val

    @classmethod
    def _parse_pattern(cls, pattern, default_pattern: str = "*") -> Pattern:
        """Internal, parse a string to pattern.
        Returns:
            Pattern: [description]
        """
        pattern = pattern or default_pattern
        if pattern is None:
            return None

        return Pattern(pattern)

    @property
    def config_preload_files(self) -> List[str]:
        if "config_preload_files" not in self:
            self.config_preload_files = []
        return self.get("config_preload_files", [])

    @config_preload_files.setter
    def config_preload_files(self, val: List[str]):
        self["config_preload_files"] = val

    @property
    def jinja_files(self) -> Pattern:
        """The pattern to match files that require jinja templeting."""
        return self._parse_pattern(self.get("jinja_files", None))

    @jinja_files.setter
    def jinja_files(self, val: Pattern):
        """Sets the pattern to match files that require jinja templeting."""
        self["jinja_files"] = str(val)

    @property
    def macros_subpath(self) -> str:
        """The suboath to the macros directory."""
        return self.get("macros_subpath", "macros")

    @macros_subpath.setter
    def macros_subpath(self, val: str):
        """The suboath to the macros directory."""
        self["macros_subpath"] = val

    @property
    def macro_files_pattern(self) -> Pattern:
        """The pattern to match files that are macro files."""
        return self._parse_pattern(self.get("macro_files_pattern", None))

    @macro_files_pattern.setter
    def macro_files_pattern(self, val: Pattern):
        """The pattern to match files that are macro files."""
        self["macro_files_pattern"] = str(val)

    @property
    def src_subpath(self) -> str:
        """The subpath to the template source directory."""
        val = self.get("src_subpath", "public").strip()
        if len(val) > 0:
            return val
        return None

    @src_subpath.setter
    def src_subpath(self, val: str):
        """The subpath to the template source directory."""
        self["src_subpath"] = val

    def save(self, config_path):
        """Save this configuration to file."""
        raise NotImplementedError()


class FilebaseApiConfigMimeTypes(SerializableDict):
    def __init__(self, **kwargs):
        """A dictionary of file types to mime types."""
        super().__init__()

        init_types = {
            "*.html": "text/html",
            "*.csv": "text/csv",
            "*.css": "text/css",
            "*.js": "text/javascript",
            "*.zip|*.rar|*.gzip|*.tar|*.tar.gz": "application/zip",
            "*.apng": "image/apng",
            "*.bmp": "image/bmp",
            "*.gif": "image/gif",
            "*.ico|*.cur": "image/x-icon",
            "*.jpg|*.jpeg,": "image/jpeg",
            "*.png": "image/png",
            "*.svg": "image/svg+xml",
            "*.tif, .tiff": "image/tiff",
            "*.webp": "image/webp",
        }

        init_types.update(kwargs)

        self.update(init_types)

    def match_mime_type(self, src: str):
        """Match the mime type file pattern to the mime type.

        Args:
            src (str): [description]

        Returns:
            [type]: [description]
        """
        for key in self.keys():
            if Pattern.test(key, src):
                return self[key]
        return "text/plain"


class FilebaseApiConfig(FilebaseTemplateServiceConfig):
    @property
    def use_sessions(self) -> bool:
        return self.get("use_sessions", True)

    @use_sessions.setter
    def use_sessions(self, val: bool):
        self["use_sessions"] = val

    @property
    def index_files(self) -> List[str]:
        """A list of index files to search for in the root directory"""
        return self.get("index_files", ["index.html", "index.htm"])

    @index_files.setter
    def index_files(self, val: List[str]):
        self["index_files"] = val

    @property
    def mime_types(self) -> FilebaseApiConfigMimeTypes:
        """The collection of mime types to file patterns"""
        mime_types = self.get("mime_types", {})
        if not isinstance(mime_types, FilebaseApiConfigMimeTypes):
            mime_types = FilebaseApiConfigMimeTypes(**mime_types)
            self["mime_types"] = mime_types
        return mime_types

    @property
    def jinja_files(self) -> Pattern:
        """The pattern to match files that require jinja templeting."""
        return self._parse_pattern(self.get("jinja_files", "*.htm?|*.css"))

    @jinja_files.setter
    def jinja_files(self, val: Pattern):
        self["jinja_files"] = str(val)

    @property
    def public_files(self) -> Pattern:
        """The pattern to match files which are public."""
        return self._parse_pattern(self.get("public_files", None))

    @public_files.setter
    def public_files(self, val: Pattern):
        self["public_files"] = str(val)

    @property
    def private_files(self) -> Pattern:
        """The pattern to match files which are private. Defaults to *.py."""
        return self._parse_pattern(self.get("private_files", "*,py"))

    @private_files.setter
    def private_files(self, val: Pattern):
        self["private_files"] = str(val)

    # -----
    @property
    def private_path_marker(self) -> Pattern:
        """The pattern to match files which are forced private by file name. Defaults to "*.private.*" """
        return self._parse_pattern(self.get("private_path_marker", "*.private.*"))

    @private_path_marker.setter
    def private_path_marker(self, val: Pattern):
        self["private_path_marker"] = str(val)

    @property
    def public_path_marker(self) -> Pattern:
        """The pattern to match files which are forced public by file name. Defaults to "*.public.*" """
        return self._parse_pattern(self.get("public_path_marker", "*.public.*"))

    @public_path_marker.setter
    def public_path_marker(self, val: Pattern):
        self["public_path_marker"] = str(val)

    @property
    def module_file_marker(self) -> Pattern:
        """The pattern to match websocket code files (module files)" """
        return self.get("module_file_marker", ".code.py")

    @module_file_marker.setter
    def module_file_marker(self, val: Pattern):
        self["module_file_marker"] = val

    @property
    def session_sqlalchemy_connection(self) -> str:
        return self.get("session_sqlalchemy_connection", None)

    @session_sqlalchemy_connection.setter
    def session_sqlalchemy_connection(self, val: str):
        self["session_sqlalchemy_connection"] = val

    @property
    def oauth_providers(self) -> List[str]:
        if "oauth_providers" not in self:
            self["oauth_providers"] = []
        return self.get("oauth_providers")

    @oauth_providers.setter
    def oauth_providers(self, val: List[str]):
        self["oauth_providers"] = val

    @property
    def oauth_clients(self) -> Dict[str, str]:
        if "oauth_clients" not in self:
            self["oauth_clients"] = FILEBASE_API_OAUTH_DEFAULT_PROVIDERS.copy()
        return self.get("oauth_clients")

    @oauth_clients.setter
    def oauth_clients(self, val: Dict[str, str]):
        self["oauth_clients"] = val

    @property
    def oauth_path_match(self) -> str:
        return self.get("oauth_path_match", "*")

    @oauth_path_match.setter
    def oauth_path_match(self, val: str):
        self["oauth_path_match"] = val

    @property
    def oauth_login_page(self) -> str:
        return self.get("oauth_login_page", f"{FILEBASE_API_CORE_PAGES_MARKER}/oauth.html")

    @oauth_login_page.setter
    def oauth_login_page(self, val: str):
        self["oauth_login_page"] = val

    @property
    def oauth_active(self) -> bool:
        return self.oauth_path_match is not None and len(self.oauth_providers) > 0

    def is_private(self, path: str) -> bool:
        """Helper, check if a path is private."""
        return self.private_files.test(path)

    def is_public(self, path: str) -> bool:
        """Helper, check if a path is public."""
        return self.public_files.test(path)

    def is_remote_access_allowed(self, path: str):
        """Helper, check if remote access is allowed for this file."""
        return self.public_path_marker.test(path) or self.is_public(path) and not self.is_private(path)


class FilebaseApiRemoteMethodConfig(SerializableDict):
    @property
    def expose_js_method(self) -> bool:
        return self.get("expose_js_method", True)
