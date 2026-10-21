import io
import json
import unittest
from unittest.mock import patch
from fuentes_es.betfair_exchange import rpc, snapshot

class FakeResponse:
    def __init__(self, payload):
        self.data = io.BytesIO(json.dumps(payload).encode())
    def __enter__(self): return self.data
    def __exit__(self, *args): pass

class ConnectorTests(unittest.TestCase):
    def test_no_keys(self):
        with self.assertRaises(ValueError):
            rpc("listMarketBook", {}, app_key="", session_token="x")
    def test_method_allowlist(self):
        with self.assertRaises(ValueError):
            rpc("placeOrders", {}, app_key="a", session_token="b")
    def test_error(self):
        def opener(req, timeout):
            return FakeResponse({"error": {"message": "INVALID_SESSION_INFORMATION"}})
        with self.assertRaises(RuntimeError):
            rpc("listMarketBook", {}, app_key="a", session_token="b", opener=opener)
    def test_only_open_prematch_returns_delayed_unverified(self):
        calls = iter([
            {"result": [{"marketId": "1.1", "event": {"name": "A vs B"},
                          "runners": [{"selectionId": 1, "runnerName": "A"},
                                      {"selectionId": 2, "runnerName": "B"}]}]},
            {"result": [{"marketId": "1.1", "status": "OPEN", "inplay": False,
                         "runners": [{"selectionId": 1, "status": "ACTIVE",
                                       "ex": {"availableToBack": [{"price": 2.0, "size": 50}]}},
                                     {"selectionId": 2, "status": "ACTIVE",
                                       "ex": {"availableToBack": [{"price": 2.1, "size": 40}]}}]}]}
        ])
        def opener(req, timeout):
            self.assertEqual(req.full_url, "https://api.betfair.com/exchange/betting/json-rpc/v1")
            self.assertNotIn(b"placeOrders", req.data)
            return FakeResponse(next(calls))
        result = snapshot(app_key="a", session_token="b", opener=opener)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["runners"]), 2)
        self.assertFalse(result[0]["eligible_for_alerts"])
        self.assertEqual(result[0]["jurisdiction"], "UNVERIFIED")
        self.assertTrue(result[0]["price_delayed_possible"])
    def test_exclude_live(self):
        calls = iter([
            {"result": [{"marketId": "1.1", "runners": []}]},
            {"result": [{"marketId": "1.1", "status": "OPEN", "inplay": True, "runners": []}]}
        ])
        self.assertEqual(snapshot(app_key="a", session_token="b",
                         opener=lambda req,timeout: FakeResponse(next(calls))), [])

if __name__ == "__main__": unittest.main()
