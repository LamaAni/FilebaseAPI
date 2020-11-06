#!/usr/bin/env python3
import logging
from zcommon.shell import logger
from filebase_api import WebServer
from filebase_api.session.sqlalchemy_session_interface import SqlAlchemySessionInterface


logger.setLevel(logging.DEBUG)
logger.info("Starting global server...")
sql_alchemy_conn = SqlAlchemySessionInterface.create_valid_sqlite_connection_string("../.local/sessions.db")
# sql_alchemy_conn = None

global_server = WebServer.start_global_web_server(
    root_path="./tester",
    port=3000,
    session_sqlalchemy_connection=sql_alchemy_conn,
)

logger.info("Started.")
global_server.join()
