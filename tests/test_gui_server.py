import json
import threading
import urllib.request

from physical_agent.gui import make_server


def _request(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def test_gui_http_demo_endpoint(tmp_path):
    server = make_server(tmp_path / "physical-agent.yaml", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        setup = _request(f"{base_url}/api/setup", method="POST", payload={})
        assert setup["ok"] is True

        demo = _request(f"{base_url}/api/demo", method="POST", payload={})
        assert demo["ok"] is True
        assert demo["executed"] == 2
        assert demo["state"]["world"]["state"]["objects"]["red_block"]["location"] == "tray"

        state = _request(f"{base_url}/api/state")
        assert state["ready"] is True
        assert state["actions"]["completed"][-1]["capability"] == "place"
    finally:
        server.shutdown()
        server.server_close()

