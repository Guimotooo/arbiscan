import unittest
from datetime import datetime,timezone,timedelta
from fuentes_es.oddspapi_multisport import (
    SPORTS,BOOKS,choose_sport,choose_tournaments,valid_prices,evaluate_fixture,
    join_results,scan,double_check,signature
)
NOW=datetime(2026,10,21,17,tzinfo=timezone.utc)

def fixture(sport=SPORTS[0]):
    sid,_,market_id,outcomes,_=sport
    labels=list(outcomes)
    def book(prices):
        return {"bookmakerIsActive":True,"suspended":False,"markets":{
          market_id:{"marketActive":True,"outcomes":{
           oid:{"players":{"0":{"price":value,"active":True,"changedAt":NOW.isoformat()}}}
           for oid,value in zip(labels,prices)}}}}
    is3=len(labels)==3
    odds={
      "bet365.es":book([3.8,3.7,1.8] if is3 else [2.2,1.8]),
      "winamax.es":book([1.8,3.0,3.8] if is3 else [1.8,2.2]),
      "betfair.es":book([1.7,2.9,3.5] if is3 else [1.7,2.1]),
      "bwin.es":book([1.6,2.8,3.3] if is3 else [1.6,2.0]),
      "codere.es":book([1.5,2.7,3.2] if is3 else [1.5,1.9]),
    }
    return {"fixtureId":"x1","sportId":sid,"statusId":0,"tournamentId":17,
            "startTime":(NOW+timedelta(days=1)).isoformat(),
            "participant1Id":1,"participant2Id":2,
            "participant1Name":"Equipo A","participant2Name":"Equipo B",
            "bookmakerOdds":odds}

class Tests(unittest.TestCase):
    def test_sports(self):
        self.assertEqual([x[0] for x in SPORTS],[10,11,12,14])
        self.assertEqual(len(BOOKS),5)
    def test_2way_arbitrage_each_sport(self):
        for sport in SPORTS[1:]:
            with self.subTest(sport=sport[1]):
                x=evaluate_fixture(fixture(sport),sport,NOW)
                self.assertIsNotNone(x)
                self.assertEqual(len(x["offers"]),2)
                self.assertGreater(x["roi_percent"],0)
    def test_3way_soccer(self):
        x=evaluate_fixture(fixture(),SPORTS[0],NOW)
        self.assertIsNotNone(x)
        self.assertEqual(len(x["offers"]),3)
    def test_reject_missing_book(self):
        f=fixture(SPORTS[1])
        f["bookmakerOdds"]={"bet365.es":f["bookmakerOdds"]["bet365.es"]}
        self.assertIsNone(evaluate_fixture(f,SPORTS[1],NOW))
    def test_reject_started_or_expired(self):
        f=fixture(SPORTS[1]);f["statusId"]=2
        self.assertIsNone(evaluate_fixture(f,SPORTS[1],NOW))
        f["statusId"]=0;f["startTime"]=(NOW-timedelta(minutes=1)).isoformat()
        self.assertIsNone(evaluate_fixture(f,SPORTS[1],NOW))
    def test_reject_wrong_market(self):
        f=fixture(SPORTS[1]);f["sportId"]=12
        self.assertIsNone(evaluate_fixture(f,SPORTS[1],NOW))
    def test_reject_suspended(self):
        f=fixture(SPORTS[1])
        for v in f["bookmakerOdds"].values():v["suspended"]=True
        self.assertIsNone(evaluate_fixture(f,SPORTS[1],NOW))
    def test_merge(self):
        f=fixture(SPORTS[2])
        feeds={b:[{**f,"bookmakerOdds":{b:f["bookmakerOdds"][b]}}] for b in BOOKS}
        out=join_results(feeds)
        self.assertEqual(len(out),1);self.assertEqual(len(out[0]["bookmakerOdds"]),5)
        self.assertIsNotNone(evaluate_fixture(out[0],SPORTS[2],NOW))
    def test_confirm_only_same_odds(self):
        f=fixture(SPORTS[2]);a=evaluate_fixture(f,SPORTS[2],NOW)
        self.assertEqual(len(double_check([a],[a],NOW)),1)
        f["bookmakerOdds"]["winamax.es"]["markets"]["121"]["outcomes"]["122"]["players"]["0"]["price"]=1.8
        b=evaluate_fixture(f,SPORTS[2],NOW)
        self.assertFalse(double_check([a],[b] if b else [],NOW))
    def test_tournament_rotation_no_popularity(self):
        t=[{"tournamentId":i,"upcomingFixtures":1,"futureFixtures":0} for i in range(1,25)]
        selected=choose_tournaments(t,NOW)
        self.assertEqual(len(selected),6)
        self.assertEqual(len(set(selected)),6)
        self.assertNotEqual(selected,choose_tournaments(t,NOW+timedelta(days=1)))
    def test_empty_tournaments(self):
        self.assertEqual(choose_tournaments([{"tournamentId":2,"futureFixtures":0}],NOW),[])
if __name__=="__main__":unittest.main()
