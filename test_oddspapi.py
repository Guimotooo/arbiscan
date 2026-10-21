import unittest
from datetime import datetime, timedelta, timezone
from fuentes_es.oddspapi import quotes_for_fixture,scan,remaining_quota,call,merge_bookmaker_fixtures,confirm_candidates

NOW=datetime(2026,10,21,16,0,tzinfo=timezone.utc)
def fixture(draw_price=3.8, status=0, changed=None, updated=None):
    changed=(changed or NOW).isoformat()
    def book(home,draw,away):
        return {"bookmakerIsActive":True,"suspended":False,"markets":{"101":{
          "marketActive":True,"outcomes":{
           k:{"players":{"0":{"active":True,"price":price,"changedAt":changed}}}
           for k,price in zip(("101","102","103"),(home,draw,away))}}}}
    return {"sportId":10,"statusId":status,"fixtureId":"f1",
            "startTime":(NOW+timedelta(hours=2)).isoformat(),
            "updatedAt":(updated or NOW).isoformat(),
            "participant1Name":"Casa","participant2Name":"Fuera",
            "bookmakerOdds":{"bet365.es":book(3.6,draw_price,1.8),
                             "winamax.es":book(1.8,3.0,3.8)}}
class TestOddspapi(unittest.TestCase):
    def test_detects_cross_book_arbitrage(self):
        opp=quotes_for_fixture(fixture(),NOW)
        self.assertIsNotNone(opp)
        self.assertGreater(opp["profit"],0)
        self.assertEqual(len({x["bookmaker"] for x in opp["offers"]}),2)
    def test_rejects_old_quote(self):
        self.assertIsNone(quotes_for_fixture(fixture(changed=NOW-timedelta(days=8)), NOW))
    def test_unchanged_price_is_not_stale(self):
        self.assertIsNotNone(quotes_for_fixture(fixture(changed=NOW-timedelta(hours=3)),NOW))
    def test_event_metadata_not_price_freshness(self):
        self.assertIsNotNone(quotes_for_fixture(fixture(updated=NOW-timedelta(hours=3)),NOW))
    def test_second_quote_must_match(self):
        a=quotes_for_fixture(fixture(), NOW)
        b=quotes_for_fixture(fixture(draw_price=4.2),NOW)
        self.assertEqual(confirm_candidates([a], [b], NOW.isoformat()),[])
        self.assertEqual(len(confirm_candidates([a], [a], NOW.isoformat())),1)
    def test_rejects_started(self):
        self.assertIsNone(quotes_for_fixture(fixture(status=2),NOW))
    def test_rejects_suspend(self):
        f=fixture()
        f["bookmakerOdds"]["winamax.es"]["suspended"]=True
        self.assertIsNone(quotes_for_fixture(f,NOW))
    def test_no_two_books(self):
        f=fixture()
        del f["bookmakerOdds"]["winamax.es"]
        self.assertIsNone(quotes_for_fixture(f,NOW))
    def test_rejects_wrong_market(self):
        f=fixture()
        for book in f["bookmakerOdds"].values():
            book["markets"]["999"]=book["markets"].pop("101")
        self.assertIsNone(quotes_for_fixture(f,NOW))
    def test_invalid_response_fails(self):
        with self.assertRaises(ValueError):
            scan({"data":{}},NOW)
    def test_quota_safety(self):
        sub={"is_active":True,"subscription_id":"a","bookmakers":{"bet365.es":{}, "winamax.es":{}},
             "request_limit":250,"request_count":240}
        self.assertEqual(remaining_quota({"current_subscription_id":"a","subscriptions":[sub]}),10)
        sub["bookmakers"]={"bet365.es":{}}
        self.assertEqual(remaining_quota({"current_subscription_id":"a","subscriptions":[sub]}),0)
    def test_merge_two_bookmakers_exact_fixture(self):
        f=fixture()
        left={**f,"bookmakerOdds":{"bet365.es":f["bookmakerOdds"]["bet365.es"]}}
        right={**f,"bookmakerOdds":{"winamax.es":f["bookmakerOdds"]["winamax.es"]}}
        merged=merge_bookmaker_fixtures({"bet365.es":[left],"winamax.es":[right]})
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0]["bookmakerOdds"]),2)
        self.assertIsNotNone(quotes_for_fixture(merged[0],NOW))
    def test_reject_conflicting_fixture(self):
        f=fixture()
        left={**f,"bookmakerOdds":{"bet365.es":f["bookmakerOdds"]["bet365.es"]}}
        right={**f,"startTime":(NOW+timedelta(days=1)).isoformat(),
              "bookmakerOdds":{"winamax.es":f["bookmakerOdds"]["winamax.es"]}}
        with self.assertRaises(ValueError):
            merge_bookmaker_fixtures({"bet365.es":[left],"winamax.es":[right]})
    def test_cannot_call_arbitrary_endpoint(self):
        with self.assertRaises(ValueError):
            call("account/refresh-api-key",{},"key")
if __name__=="__main__": unittest.main()
