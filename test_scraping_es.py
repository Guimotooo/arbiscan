import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from scraping_es.browser_scan import validate_config,parse_price,compare,recheck_same

NOW=datetime(2026,10,21,19,0,tzinfo=timezone.utc)
def snapshot(book, event="A vs B"):
    return {"book":book,"event":event,"kickoff":(NOW+timedelta(days=1)).isoformat(),
            "market":"1X2_90_MIN","source_url":"https://"+book+"/x",
            "prices":{"home":3.9 if book=="bet365.es" else 1.8,
                      "draw":3.7 if book=="bet365.es" else 3.3,
                      "away":1.9 if book=="bet365.es" else 3.9}}
class Tests(unittest.TestCase):
    def test_price(self):
        self.assertEqual(parse_price("2,15"),2.15)
        for value in ("2,1.0","x2.00","2.1 3.4","0.9"):
            with self.assertRaises(ValueError): parse_price(value)
    def test_valid_candidate(self):
        result=compare(snapshot("bet365.es"),snapshot("winamax.es"))
        self.assertIsNotNone(result)
        self.assertGreater(result["profit"],0)
    def test_event_mismatch(self):
        self.assertIsNone(compare(snapshot("bet365.es"),snapshot("winamax.es","C vs D")))
    def test_unconfirmed_change(self):
        a=compare(snapshot("bet365.es"),snapshot("winamax.es"))
        b=deepcopy(snapshot("winamax.es"))
        b["prices"]["away"]=4.1
        c=compare(snapshot("bet365.es"),b)
        self.assertFalse(recheck_same(a,c))
    def test_config_hosts(self):
        selectors={k:".sample" for k in ("event","start","home","draw","away")}
        good={name:{"url":"https://"+name+"/match","market":"1X2_90_MIN","selectors":selectors}
              for name in ("bet365.es","winamax.es")}
        self.assertEqual(validate_config(good),good)
        fragment=deepcopy(good)
        fragment["bet365.es"]["url"]="https://www.bet365.es/#/AC/B1/C1/D8/E202645795/F3/I1/P30024/H1/"
        self.assertEqual(validate_config(fragment),fragment)
        bad=deepcopy(good)
        bad["bet365.es"]["url"]="https://evil.example/path"
        with self.assertRaises(ValueError):validate_config(bad)
        bad=deepcopy(good)
        bad["winamax.es"]["url"]="http://winamax.es/match"
        with self.assertRaises(ValueError):validate_config(bad)
if __name__=="__main__":unittest.main()
