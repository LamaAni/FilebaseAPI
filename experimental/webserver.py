#!/usr/bin/env python3
import logging
from zcommon.shell import logger
from zcommon.fs import relative_abspath
from filebase_api import WebServer, FilebaseApiConfig
from filebase_api.session.sqlalchemy_session_interface import SqlAlchemySessionInterface


logger.setLevel(logging.DEBUG)
logger.info("Starting global server...")
sql_alchemy_conn = SqlAlchemySessionInterface.create_valid_sqlite_connection_string("../.local/sessions.db")

# sql_alchemy_conn = None
config = FilebaseApiConfig()
config.session_sqlalchemy_connection = sql_alchemy_conn
config.oauth_providers = ["google"]
config.config_preload_files.append(relative_abspath("../.local/tester.filebase_api.yaml"))

global_server = WebServer.start_global_web_server(
    root_path="./tester",
    port=3000,
    config=config,
)

logger.info("Started.")
global_server.join()
