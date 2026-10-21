import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,MagicMock

from scraping_es.scrapling_adapter import parse_html,fetch_public_html,scan_single_match
from scraping_es.browser_scan import MARKET,compare
NOW=datetime(2026,10,21,19,0,tzinfo=timezone.utc)
def config(brand):
    return {"url":"https://www."+brand+"/match",
            "market":MARKET,
            "selectors":{"event":"h1.event","start":"time.start","home":"span.home","draw":"span.draw","away":"span.away"}}
def html(event="Team A vs Team B", price="3.90", duplicate=False):
    kickoff=(NOW+timedelta(days=1)).isoformat()
    return (f'<main><h1 class="event">{event}</h1><time class="start">{kickoff}</time>'
            f'<section><span class="home">{price}</span><span class="draw">3.60</span>'
            f'<span class="away">3.70</span>{"<span class=home>2.0</span>" if duplicate else ""}</section></main>')

class Tests(unittest.TestCase):
    def test_parses_precise_three_way_market(self):
        a=parse_html(html(),"bet365.es",config("bet365.es"),NOW)
        self.assertEqual(a["prices"]["home"],3.9)
        self.assertEqual(a["market"],MARKET)
    def test_rejects_ambiguous_quote_or_match(self):
        with self.assertRaises(ValueError):
            parse_html(html(duplicate=True),"winamax.es",config("winamax.es"),NOW)
    def test_rejects_nondecimal_quote(self):
        with self.assertRaises(ValueError):
            parse_html(html(price="2/1"),"bet365.es",config("bet365.es"),NOW)
    def test_rejects_access_challenge(self):
        with self.assertRaises(ValueError):
            parse_html("<body>Captcha verify you are human</body>","bet365.es",config("bet365.es"),NOW)
    def test_rejects_wrong_sport_or_event(self):
        a=parse_html(html("A vs B"),"bet365.es",config("bet365.es"),NOW)
        b=parse_html(html("C vs D"),"winamax.es",config("winamax.es"),NOW)
        self.assertIsNone(compare(a,b))
    def test_only_allowlisted_sites(self):
        with self.assertRaises(ValueError):
            fetch_public_html("bet365.es","https://other.example/match")
    def test_fail_closed_http(self):
        with patch("scrapling.fetchers.Fetcher.get") as get:
            fake=MagicMock()
            fake.status=403;fake.url="https://www.winamax.es/match";fake.body=b"Blocked"
            get.return_value=fake
            with self.assertRaisesRegex(ValueError,"HTTP 403"):
                fetch_public_html("winamax.es","https://www.winamax.es/match")
if __name__=="__main__": unittest.main()
