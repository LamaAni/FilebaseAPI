import re
import os
from typing import Type, List, Union
from datetime import datetime, timedelta
from sanic_session.base import BaseSessionInterface

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import sessionmaker, scoped_session, Query
from sqlalchemy import Column, String, Index, DateTime, MetaData, create_engine

from sqlalchemy.ext.declarative import declarative_base
from zthreading.decorators import collect_delayed_calls_async
from zcommon.fs import relative_abspath

FilebaseApiModelBase = declarative_base(
    metadata=MetaData(schema="filebaseapi"),
)


class SqlAlchemySessionInterfaceException(Exception):
    pass


class SqlAlchemySessionModel:
    key = Column(String, primary_key=True)
    data = Column(String())
    expires = Column(DateTime())


class SqlAlchemySessionInterface(BaseSessionInterface):
    def __init__(
        self,
        sql_alchemy_connection: str,
        sql_alchemy_schema: str = "filebaseapi",
        sql_alchemy_table_name: str = "sessions",
        sql_alchemy_engine_args: dict = {},
        auto_extend_session_expires: bool = False,
        create_indexis: bool = True,
        domain: str = None,
        expiry: int = 2592000,
        httponly: bool = True,
        cookie_name: str = "session",
        prefix: str = "session:",
        sessioncookie: bool = False,
        samesite: str = None,
        session_name="session",
        secure: bool = False,
    ) -> None:
        super().__init__(
            expiry=expiry,
            prefix=prefix,
            cookie_name=cookie_name,
            domain=domain,
            httponly=httponly,
            sessioncookie=sessioncookie,
            samesite=samesite,
            session_name=session_name,
            secure=secure,
        )
        self.auto_extend_session_expires = auto_extend_session_expires
        self._sql_alchemy_connection = sql_alchemy_connection
        self._sql_alchemy_schema = sql_alchemy_schema
        self._sql_alchemy_engine_args = sql_alchemy_engine_args
        self._sql_alchemy_table_name = sql_alchemy_table_name
        self._data_model: Type[SqlAlchemySessionModel] = None
        self._engine: Engine = None
        self._scoped_session: scoped_session = None
        self._create_indexis = create_indexis

    @property
    def sql_alchemy_table_name(self) -> str:
        return self.sql_alchemy_table_name

    @property
    def sql_alchemy_engine(self) -> Engine:
        self._assert_sql_alchemy()
        return self._engine

    @property
    def data_model(self) -> Type[Union[SqlAlchemySessionModel, FilebaseApiModelBase]]:
        self._assert_sql_alchemy()
        return self._data_model

    @property
    def sql_alchemy_scoped_session(self) -> scoped_session:
        self._assert_sql_alchemy()
        return self._scoped_session

    @property
    def sql_alchemy_connection(self) -> str:
        self._assert_sql_alchemy()
        return self._sql_alchemy_connection

    def _assert_sql_alchemy(self):
        if self._data_model is not None:
            return
        self._init_sql_alchemy()

    def _init_sql_alchemy(self):
        table_args = {}
        if not re.match(r".*([^\w]|^)sqlite([^\w].*|)[:][\/]{2}", self._sql_alchemy_connection):
            table_args["schema"] = self._sql_alchemy_schema

        class _Internal_SqlAlchemySessionInterface(SqlAlchemySessionModel, FilebaseApiModelBase):
            __tablename__ = self._sql_alchemy_table_name
            __table_args__ = table_args
            metadata = MetaData()

        if self._create_indexis:
            Index("session_key", _Internal_SqlAlchemySessionInterface.key)
            Index("session_expires", _Internal_SqlAlchemySessionInterface.expires)

        self._data_model = _Internal_SqlAlchemySessionInterface
        args = {
            "encoding": "utf-8",
        }
        args.update(self._sql_alchemy_engine_args)
        self._engine = create_engine(self.sql_alchemy_connection, **args)
        self._scoped_session = scoped_session(
            sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self._engine,
                expire_on_commit=False,
            )
        )
        # create the tables and schemas
        _Internal_SqlAlchemySessionInterface.metadata.create_all(bind=self._engine)

    def new_session(self) -> SqlAlchemySession:
        return self.sql_alchemy_scoped_session()

    def new_query(self, session: SqlAlchemySession = None) -> Query:
        return (session or self.sql_alchemy_scoped_session()).query(self.data_model)

    @collect_delayed_calls_async(interval=0.5)
    def _clean_expired_sessions(self):
        pass

    @classmethod
    def to_session_key(cls, prefix: str, sid: str):
        return "".join([v for v in [prefix, sid] if v is not None])

    def get_session_object(self, key: str, session: SqlAlchemySession = None) -> SqlAlchemySessionModel:
        all_vals: List[SqlAlchemySessionModel] = self.new_query().filter(self.data_model.key == key).all()
        assert len(all_vals) < 2, SqlAlchemySessionInterfaceException("To sessions match the same key: " + key)
        return None if len(all_vals) == 0 else all_vals[0]

    async def _get_value(self, prefix: str, sid: str):
        return self._get_value_sync(prefix=prefix, sid=sid)

    def _get_value_sync(self, prefix: str, sid: str):
        session_data = self.get_session_object(self.to_session_key(prefix, sid))
        if session_data is None:
            return None

        data = session_data.data
        assert data is None or isinstance(data, str), SqlAlchemySessionInterfaceException(
            "Invalid session data. data: " + data
        )
        return data

    async def _delete_key(self, key: str):
        self._delete_key_sync(key=key)

    def _delete_key_sync(self, key):
        try:
            session = self.new_session()
            self.new_query(session=session).filter(self.data_model.key == key).delete()
            session.commit()
        except Exception as ex:
            raise SqlAlchemySessionInterfaceException(**ex.args)

    async def _set_value(self, key: str, data: dict):
        self._set_value_sync(key=key, data=data)

    def _set_value_sync(self, key: str, data: str):
        assert data is None or isinstance(data, str), SqlAlchemySessionInterfaceException(
            "Session data must be a string"
        )

        try:
            session = self.new_session()
            data_obj = self.get_session_object(key, session=session)
            if data_obj is None:
                data_obj = self.data_model(
                    key=key,
                    data=data,
                    expires=datetime.now() + timedelta(seconds=self.expiry),
                )
            else:
                if self.auto_extend_session_expires:
                    self.data_model.expires = datetime.now() + timedelta(seconds=self.expiry)
                self.data = data
            session.merge(data_obj)
            session.commit()
        except Exception as ex:
            raise SqlAlchemySessionInterfaceException("Failed to set session value", ex)

    @classmethod
    def create_valid_sqlite_connection_string(cls, relative_path: str, auto_make_dirs=True):
        db_path = relative_abspath(relative_path, call_stack_offset=2)
        conn_string = "sqlite:///" + db_path
        if auto_make_dirs:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return conn_string

    @classmethod
    def create_sqlite_interpenter(cls, relative_path: str, auto_make_dirs=True):
        return cls(
            cls.create_valid_sqlite_connection_string(relative_path=relative_path, auto_make_dirs=auto_make_dirs)
        )
