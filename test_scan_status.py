import io
import json
import unittest
from unittest.mock import Mock
from fuentes_es.scan_status import publish_scan_status

class Reply:
    status=200
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,*args): return b'{"ok":true}'

class ScanStatusTests(unittest.TestCase):
    def test_auth_and_real_counts_sent_to_worker(self):
        requests=[]
        def opener(req,timeout):
            requests.append(req)
            return Reply()
        result=publish_scan_status(
            worker_url="https://arbiscan.example.workers.dev",
            secret="secret",state="finished",books=["bet365.es","winamax.es"],
            fixture_count=36,candidates=0,confirmed=0,sent=0,opener=opener)
        self.assertTrue(result)
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0].get_method(),"POST")
        data=json.loads(requests[0].data)
        self.assertEqual(data["fixture_count"],36)
        self.assertEqual(data["state"],"finished")
        self.assertEqual(data["books"],["bet365.es","winamax.es"])
    def test_no_secret_prevents_requests(self):
        callback=Mock()
        self.assertFalse(publish_scan_status(
            worker_url="https://arbiscan.example.workers.dev",
            secret="",state="finished",opener=callback))
        callback.assert_not_called()
    def test_external_url_rejected(self):
        callback=Mock()
        self.assertFalse(publish_scan_status(
            worker_url="https://attacker.example.com",
            secret="secret",state="finished",opener=callback))
        callback.assert_not_called()
    def test_invalid_count_rejected(self):
        with self.assertRaises(ValueError):
            publish_scan_status(worker_url="https://arbiscan.example.workers.dev",
              secret="secret",state="finished",fixture_count=-1)
if __name__=="__main__":
    unittest.main()
