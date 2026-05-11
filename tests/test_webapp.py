"""Tests for the local Quant Lab web app."""
import json
import threading
import urllib.request

from quant import webapp


def test_actions_are_allowlisted_commands():
    actions = webapp.actions_manifest()
    ids = {item["id"] for item in actions}
    assert {"process", "norgateStatus", "norgateImport", "norgateMetadata", "recommend", "allocate", "recordTrade", "researchPrompt", "paperSim", "workflow", "llm"}.issubset(ids)
    command = webapp.build_command("recommend", {"tickers": "AAPL,MSFT", "topN": "3"})
    assert command[:3] == [webapp.sys.executable, "-m", "quant.cli"]
    assert "recommend-v2" in command
    assert "--json-output" in command
    allocate_command = webapp.build_command("allocate", {"capital": "20000", "engine": "both"})
    assert "allocate-budget" in allocate_command
    assert "--capital" in allocate_command


def test_unknown_action_rejected():
    try:
        webapp.build_command("rm-rf", {})
    except ValueError as exc:
        assert "Unknown action" in str(exc)
    else:
        raise AssertionError("unknown action should fail")


def test_web_api_serves_workflow():
    server = webapp.ThreadingHTTPServer(("127.0.0.1", 0), webapp.QuantLabHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/workflow"
        payload = json.loads(urllib.request.urlopen(url, timeout=5).read().decode())
        assert payload["workflow"]["title"] == "Quant Lab Research Workflow"
        assert payload["blockedPhaseGuide"]
    finally:
        server.shutdown()
        server.server_close()
