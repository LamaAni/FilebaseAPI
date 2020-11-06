from datetime import datetime
from filebase_api import fapi_remote, FilebaseApiPage


@fapi_remote
def test(page: FilebaseApiPage, msg: str):
    page.session["lama"] = "kka"
    return "The message: " + msg


@fapi_remote
def test_with_defaults(page: FilebaseApiPage, msg: str, other_message: str = None):
    return {
        "msg": msg,
        "other_message": other_message,
    }


@fapi_remote
def test_interval(page: FilebaseApiPage, msg: str = "No message"):
    return {"msg": msg, "server_time": datetime.now()}


@fapi_remote
def test_session(page: FilebaseApiPage):
    session_cookie_id = page.request.cookies.get("session")
    old_val = page.session.get("val")
    val = datetime.now().isoformat()
    page.session["val"] = val
    return f"{session_cookie_id}\n{old_val} -> {val}"
