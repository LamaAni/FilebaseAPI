import json
from filebase_api.web.client import ClientRequest, ClientException


class ClientRestRequestException(ClientException):
    pass


class ClientRestRequest(ClientRequest):
    def __init__(
        self,
        path: str = "",
        base_url: str = None,
        headers: dict = None,
        params: dict = None,
        method: str = "GET",
        body: dict = None,
    ):
        headers = headers or {}
        headers.setdefault("Accept", "application/json")

        super().__init__(
            path=path,
            base_url=base_url,
            headers=headers,
            params=params,
            method=method,
            body=body,
        )

    def process_request_response(self, rsp):
        try:
            return json.loads(rsp.text) if rsp is not None else None
        except json.JSONDecodeError as ex:
            raise ClientRestRequestException("Failed to parse REST request", *ex.args)
