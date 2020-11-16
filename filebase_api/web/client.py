import json
from typing import List, Callable, Set, Dict, Union, Generator, Iterable, Mapping
from weakref import WeakSet
from match_pattern import Pattern
from zthreading.tasks import Task
from zthreading.events import EventHandler
from requests import request, Response
from urllib.parse import urlencode

from zcommon.textops import create_unique_string_id
from zcommon.collections import StringEnum, is_iterable


class ClientException(Exception):
    pass


class ClientRequestException(ClientException):
    pass


class ClientEventNames(StringEnum):
    request_complete = "request_complete"
    stop_all_requests = "stop_all_requests"


def combine_dictionaries(*args):
    d = {}
    for inner in args:
        if inner is None:
            continue
        d.update(inner)
    return d


class ClientRequest:
    def __init__(
        self,
        path: str = "",
        base_url: str = None,
        headers: dict = None,
        params: dict = None,
        method: str = "GET",
        body: dict = None,
    ):
        super().__init__()
        # assert isinstance(path, str) and len(path.strip()) > 0, ValueError("Path must be a non empty string")
        # Path is never an abs path.
        if path and Pattern.match(r"re::^[^:\/]+:\/\/", path):
            "Full url sent"
            base_url = path
            path = ""
        else:
            path = Pattern.replace(r"re::^\/", "", (path or "").strip())

        self.path = path
        self.base_url = base_url
        self.headers = headers or {}
        self.params = params or {}
        self.method = method
        self.body = body
        self._task: Task = None

    @property
    def url(self) -> str:
        """The request url.

        Returns:
            str: [description]
        """
        return f"{self.base_url}/{self.path}" if self.path.strip() else self.base_url

    @property
    def url_with_params(self) -> str:
        """The url with the query string params."""
        return self.encode_url(self.base_url, params=self.params)

    @classmethod
    def encode_url_params(cls, params: Union[str, bytes, Iterable]):
        if isinstance(params, (str, bytes)):
            return params
        elif hasattr(params, "read"):
            return params
        elif hasattr(params, "__iter__"):
            if isinstance(params, (Mapping, Dict)):
                params = params.items()

            result = []
            for k, vs in params:
                if isinstance(vs, (str, bytes)) or not hasattr(vs, "__iter__"):
                    vs = [vs]
                for v in vs:
                    if v is not None:
                        result.append(
                            (
                                k.encode("utf-8") if isinstance(k, str) else k,
                                v.encode("utf-8") if isinstance(v, str) else v,
                            )
                        )
            return urlencode(result, doseq=True)
        else:
            return params

    @classmethod
    def encode_url(cls, base_url: str, params: Union[str, bytes, Iterable]):
        return f"{base_url}?{cls.encode_url_params(params)}"

    def process_request_response(self, response: Response):
        return response

    def send_async_request(self, response_handler: Callable, use_async_loop=False, timeout: float = 5, **kwargs):
        """Synchronically sends the request to the server.

        Args:
            response_handler (Callable): The callback handler.
            use_async_loop (bool, optional): NOT YET IMPLEMENTED. Defaults to False.
            timeout (float, optional): The response timeout. Defaults to 5.
        """

        async def request_task():
            response: Response = None
            err = None
            try:
                response = request(
                    method=self.method,
                    url=self.url,
                    headers=self.headers,
                    params=self.params,
                    json=self.body,
                    timeout=timeout,
                    **kwargs,
                )
                response.raise_for_status()
            except Exception as ex:
                err = ex

            response_handler(response, err)

        self._task = Task(request_task, use_async_loop=use_async_loop).start()
        return self._task

    def parse_response(self, response: Response, err: Exception):
        try:
            response = self.process_request_response(response)
        except Exception as ex:
            if err is None:
                raise ex

        if err is not None:
            err.response = response
            err = ClientRequestException(response.text if isinstance(response, Response) else response, *err.args)
            raise err

        return response


class _ClientRequestGrp(EventHandler):
    def __init__(self, requests: List[ClientRequest]):
        """Internal, used to follow and manage a request group to allow for throttling.

        Args:
            requests (List[ClientRequest]): The requests to execute.
        """
        super().__init__()
        self.requests = list(requests) if is_iterable(requests) else [requests]
        self._completed = set()
        self.id = create_unique_string_id()
        self.on(ClientEventNames.stop_all_requests, lambda *args, **kwargs: self.stop())

    def complete_request(self, request: ClientRequest, response: Response, err: Exception):
        """Complete a single request in the group and advance the group to next
        request.

        Args:
            request (ClientRequest): The request to complete
            rsp ([type]): The request response
            err (Exception): The response error if any.
        """
        self._completed.add(request)
        try:
            response = request.parse_response(response=response, err=err)
            self.emit(ClientEventNames.request_complete, response)
        except Exception as ex:
            self.emit_error(ex)
        finally:
            if len(self._completed) == len(self.requests):
                self.stop_all_streams()

    def stop(self):
        """Stop all requests in the grp."""
        self.stop_all_streams()
        for q in self.requests:
            if q._task is not None:
                q._task.stop()


class Client:
    def __init__(
        self,
        base_url: str,
        headers: dict = None,
        params=None,
        max_parallel_requests: int = 10,
        content_type="application/json",
        parse_response=None,
    ):
        """Creates a new http client that can send multiple, parallel requests
        to a server

        Args:
            base_url (str): The server base url.
            headers (dict, optional): The headers to add. Defaults to None.
            params ([type], optional): The request params. Defaults to None.
            max_parallel_requests (int, optional): The number of max paralell requests. Defaults to 10.
            content_type (str, optional): The content type. Defaults to "application/json".
            parse_response (Callable(rsp:str), optional): A default parse response method, to be called on any response.
        """
        super().__init__()

        self.headers = headers or {}
        self.params = params or {}
        self.max_parallel_requests = max_parallel_requests
        self.parse_response = parse_response

        self._base_url = base_url
        self._task: Task = Task(lambda *args, **kwargs: self._request_loop(*args, **kwargs))
        self._is_executing_loop = False
        self._pending_request_groups: List[_ClientRequestGrp] = []
        self._executing_requests: Set[ClientRequest] = WeakSet()

        if content_type and "content_type" not in self.headers:
            self.headers["content_type"] = content_type

    @property
    def base_url(self) -> str:
        """The server base url."""
        return self._base_url

    def _request_loop(self, *args, **kwargs):
        request_sets = []

        def populate_request_sets():
            while len(self._pending_request_groups) > 0:
                grp = self._pending_request_groups.pop(0)
                for request in grp.requests:
                    request_sets.append((request, grp))

        def process_request_rslt(request: ClientRequest, grp: _ClientRequestGrp, rsp: Response, err: Exception):
            try:
                rsp = self.parse_response(rsp) if callable(self.parse_response) else rsp
            except Exception as ex:
                err = ex

            self._executing_requests.remove(request)

            try:
                grp.complete_request(request, rsp, err)
            except Exception as ex:
                self._task.emit_error(ex)

        def invoke_request(request):
            request.base_url = request.base_url or self.base_url
            request.params = combine_dictionaries(self.params, request.params)
            request.headers = combine_dictionaries(self.headers, request.headers)
            request.send_async_request(lambda rslt, err: process_request_rslt(request, grp, rslt, err))
            self._executing_requests.add(request)

        request: ClientRequest = None
        grp: _ClientRequestGrp = None
        while True:
            populate_request_sets()
            if len(request_sets) == 0:
                break
            request, grp = request_sets.pop(0)
            self._task.pipe(grp, use_weak_reference=True)

            invoke_request(request)

            if len(self._executing_requests) > self.max_parallel_requests:
                Task.wait_for_one([q._task for q in self._executing_requests])

        self._is_executing_loop = False

    def _validate_executing(self):
        if self._is_executing_loop:
            return

        self._is_executing_loop = True
        if self._task.is_running:
            # Wait for prev to complete.
            self._task.join(timeout=10)
        self._task.start()

    def _start_if_needed(self):
        if len(self._pending_request_groups) > 0:
            self._validate_executing()

    def _create_request_grp(self, requests: List[ClientRequest]) -> _ClientRequestGrp:
        grp = _ClientRequestGrp(requests)
        self._pending_request_groups.append(grp)
        self._validate_executing()
        return grp

    def stop(self, timeout: int = None):
        """Stop all executing requests

        Args:
            timeout (int, optional): The stop timeout, errors if overdue. Defaults to None.
        """
        if self._task is not None:
            self._task.emit(ClientEventNames.stop_all_requests)
            self._task.stop_all_streams()
            self._task.stop(timeout)

    def stream(
        self,
        requests: Union[ClientRequest, List[ClientRequest]],
        timeout: int = None,
        raise_errors=True,
    ) -> Generator[Union[Dict, str], None, None]:
        """Stream the results of a request, as they arrive. Causes the thread to wait. (yield)

        Args:
            requests (Union[ClientRequest, List[ClientRequest]]): The request(ies) to execute.
            timeout (int, optional): The request timeout, errors if overdue. Defaults to None.
            raise_errors (bool, optional): If false, dose not raise request errors. Defaults to True.

        Raises:
            errors: [description]
            ClientException: [description]

        Yields:
            Generator[Union[Dict, str]]: The response, depends on request processing.
        """
        grp = self._create_request_grp(requests)
        errors = []

        def handle_error(sender, err):
            errors.append(err)

        grp.on(grp.error_event_name, handle_error)

        for v in grp.stream(
            ClientEventNames.request_complete, process_event_data=lambda ev: ev.args[0], timeout=timeout
        ):
            yield v

        if raise_errors and len(errors) > 0:
            if len(errors) == 1:
                raise errors[0]
            else:
                raise ClientException("Multiple errors while streaming", *errors)

    def request(
        self,
        requests: Union[ClientRequest, List[ClientRequest]],
        timeout: int = None,
        raise_errors=True,
    ) -> Union[Union[Dict, str], List[Union[Dict, str]]]:
        """Returns a collection request results. Causes the thread to wait. (yield)

        Args:
            requests (List[ClientRequest]): The request(ies) to execute.
            timeout (int, optional): The request timeout, errors if overdue. Defaults to None.
            raise_errors (bool, optional): If false, dose not raise request errors. Defaults to True.

        Returns:
             Union[Union[Dict, str], List[Union[Dict, str]]]: The response. If requests is an array,
                will return an array.
        """
        is_single = not is_iterable(requests)
        rslt = list(self.stream(requests, timeout, raise_errors))
        if is_single:
            return None if len(rslt) == 0 else rslt[0]
        return rslt


if __name__ == "__main__":

    def parse_response_as_json(rq: ClientRequest, rsp: Response):
        try:
            return json.loads(rsp.text) if rsp is not None else None
        except json.JSONDecodeError:
            pass

    pm_echo = Client("https://postman-echo.com/get")
    print(
        pm_echo.request(
            ClientRequest(
                method="POST",
                params={
                    "lama": "kka",
                },
                process_request_rsp=parse_response_as_json,
            )
        )
    )
