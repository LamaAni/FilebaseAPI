import os
from filebase_api.session_interfaces import SqlAlchemySessionInterface
from zcommon.fs import relative_abspath

SQLITE_DB_PATH = relative_abspath("../.local/sessions.db")
SQLITE_CONNECTION_STRING = "sqlite:///" + SQLITE_DB_PATH
os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)

interface = SqlAlchemySessionInterface(sql_alchemy_connection=SQLITE_CONNECTION_STRING)
interface._init_sql_alchemy()

interface._set_value_sync("lama", {"a": "val of a", "b": [1, "2"]})
