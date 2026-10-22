import unittest
import random
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from unittest.mock import patch

from motor_propio.engine import (
    Quote,BadQuote,aware,token,decimal_odds,from_record,
    opportunities,confirm,fingerprint,alert,market_outcomes,
)
from motor_propio.web import validate_profile,parse_html,load_profiles
from motor_propio.oddspapi_adapter import convert_fixture,convert_fixtures

NOW=datetime(2026,10,22,11,0,tzinfo=timezone.utc)
START=NOW+timedelta(days=1)

def quote(book, prices, sport="soccer",market="1x2:regulation",start=START,
          observed=NOW, provider_update=None,home="Cambrian United",away="Airbus UK Broughton"):
    return Quote(
        book=book,sport=sport,home=home,away=away,kickoff=start,market=market,
        prices=prices,observed_at=observed,source="fixture_test",
        provider_updated_at=provider_update)

SOCCER_A={"1":"3.60","X":"3.80","2":"1.80"}
SOCCER_B={"1":"1.80","X":"3.00","2":"3.80"}

def profile(market="1x2:regulation", sport="soccer"):
    return {
        "book":"winamax.es","url":"https://www.winamax.es/sports-betting/match/1234",
        "sport":sport,"market":market,"mode":"html",
        "permission_confirmed":True,
        "market_scope":".market-box","market_label":"Resultado final",
        "selectors":{
            "market_heading":".market-heading",
            "home":".home","away":".away",
            "kickoff":{"css":"time.kickoff","attribute":"datetime"},
            "1":".odds-home","X":".odds-draw","2":".odds-away",
        },
    }

def sample_html(price="3,60",double=False, blocked=False):
    return ('<html><body>'+
            ("CAPTCHA verify you are human" if blocked else "")+
            '<span class="home">Cambrian United</span>'+
            '<span class="away">Airbus UK Broughton</span>'+
            '<time class="kickoff" datetime="'+START.isoformat()+'"></time>'+
            '<section class="market-box"><h2 class="market-heading">Resultado final</h2>'+ 
            '<span class="odds-home" data-odds="3.60">'+price+'</span>'+
            '<span class="odds-draw">3.80</span>'+
            '<span class="odds-away">1.80</span>'+
            ('<span class="odds-home">3.60</span>' if double else '')+
            '</section></body></html>')

def provider_fixture(sport_id=10,updated=NOW):
    mid,ids=(("101",("101","102","103")) if sport_id==10 else
             ("121",("121","122")))
    def makebook(price_list):
        return {"bookmakerIsActive":True,"suspended":False,"markets":{
            mid:{"marketActive":True,"outcomes":{
                oid:{"players":{"0":{"price":price,"changedAt":NOW.isoformat(),"active":True}}}
                for oid,price in zip(ids,price_list)}}}}
    if sport_id==10:
        prices_a=(3.6,3.8,1.8);prices_b=(1.8,3.0,3.8)
    else:
        prices_a=(2.2,1.8);prices_b=(1.8,2.2)
    return {"fixtureId":"fxx","sportId":sport_id,"statusId":0,
            "startTime":START.isoformat(),"updatedAt":updated.isoformat(),
            "participant1Name":"Cambrian United","participant2Name":"Airbus UK Broughton",
            "bookmakerOdds":{"bet365.es":makebook(prices_a),
                             "winamax.es":makebook(prices_b)}}

class EngineTests(unittest.TestCase):
    def test_normalize_names_accents(self):
        self.assertEqual(token("  CÀMBRIAN--UNITED!!"),"cambrian united")
        self.assertEqual(aware("2026-10-22T12:00:00+01:00"),NOW)
    def test_reject_naive_dates(self):
        with self.assertRaises(BadQuote):aware("2026-10-22T12:00:00")
    def test_valid_decimal_odds(self):
        self.assertEqual(decimal_odds("2,80"),Decimal("2.80"))
    def test_reject_odds_fractions_nan_and_bools(self):
        for raw in ("2/1","1.000.00","NaN","inf","-2","3x",True,1000):
            with self.subTest(raw=raw):
                with self.assertRaises(BadQuote):decimal_odds(raw)
    def test_reject_missing_outcome(self):
        with self.assertRaises(BadQuote):quote("winamax.es",{"1":2,"X":3})
    def test_reject_same_team(self):
        with self.assertRaises(BadQuote):
            quote("winamax.es",SOCCER_A,away="Cambrian United")
    def test_reject_wrong_sport_market(self):
        with self.assertRaises(BadQuote):
            quote("winamax.es",SOCCER_A,sport="tennis")
    def test_find_surebet_rounding(self):
        opp=opportunities([quote("bet365.es",SOCCER_A),
                           quote("winamax.es",SOCCER_B)],NOW)
        self.assertEqual(len(opp),1)
        self.assertGreater(Decimal(opp[0]["profit"]),0)
        self.assertEqual(sum(Decimal(x["stake"]) for x in opp[0]["offers"]),Decimal("100"))
        self.assertGreaterEqual(min(Decimal(x["stake"])*Decimal(x["price"])
                                 for x in opp[0]["offers"]),Decimal("100"))
        self.assertEqual(set(x["outcome"] for x in opp[0]["offers"]),{"1","X","2"})
        self.assertIn("SIN CONFIRMAR",alert(opp[0]))
    def test_too_small_roi_rejected_after_rounding(self):
        a=quote("bet365.es",{"1":2,"X":3.0,"2":3.0})
        b=quote("winamax.es",{"1":2,"X":3.0,"2":3.0})
        self.assertFalse(opportunities([a,b],NOW))
    def test_reject_different_events(self):
        b=quote("winamax.es",SOCCER_B,away="Other Football Club")
        self.assertEqual(opportunities([quote("bet365.es",SOCCER_A),b],NOW),[])
    def test_reject_swapped_home_away(self):
        a=quote("bet365.es",SOCCER_A)
        b=quote("winamax.es",SOCCER_B,home=a.away,away=a.home)
        self.assertEqual(opportunities([a,b],NOW),[])
    def test_reject_event_different_kickoff(self):
        a=quote("bet365.es",SOCCER_A)
        b=quote("winamax.es",SOCCER_B,start=START+timedelta(minutes=4))
        self.assertFalse(opportunities([a,b],NOW))
    def test_accept_event_two_minute_offset(self):
        a=quote("bet365.es",SOCCER_A)
        b=quote("winamax.es",SOCCER_B,start=START+timedelta(seconds=90))
        self.assertTrue(opportunities([a,b],NOW))
    def test_duplicate_same_book_is_unsafe(self):
        a=quote("bet365.es",SOCCER_A)
        b=quote("winamax.es",SOCCER_B)
        self.assertFalse(opportunities([a,a,b],NOW))
    def test_stale_observed_rejected(self):
        a=quote("bet365.es",SOCCER_A,observed=NOW-timedelta(minutes=10))
        b=quote("winamax.es",SOCCER_B)
        self.assertFalse(opportunities([a,b],NOW))
    def test_future_observation_rejected(self):
        a=quote("bet365.es",SOCCER_A,observed=NOW+timedelta(minutes=1))
        self.assertFalse(opportunities([a,quote("winamax.es",SOCCER_B)],NOW))
    def test_stale_provider_metadata_rejected(self):
        a=quote("bet365.es",SOCCER_A,provider_update=NOW-timedelta(days=1))
        b=quote("winamax.es",SOCCER_B)
        self.assertFalse(opportunities([a,b],NOW))
    def test_cannot_compare_different_settlement_rules(self):
        a=quote("bet365.es",{"1":"2.20","2":"1.80"},"tennis","winner:completed_match")
        b=quote("winamax.es",{"1":"1.80","2":"2.20"},"tennis","winner:retirement_counts")
        self.assertFalse(opportunities([a,b],NOW))
    def test_two_way_surebet(self):
        a=quote("bet365.es",{"1":"2.20","2":"1.80"},"basketball","winner:including_ot")
        b=quote("winamax.es",{"1":"1.80","2":"2.20"},"basketball","winner:including_ot")
        self.assertTrue(opportunities([a,b],NOW))
    def test_total_half_point_markets(self):
        a=quote("bet365.es",{"OVER":"2.20","UNDER":"1.75"},
                "soccer","total:regulation:2.5")
        b=quote("winamax.es",{"OVER":"1.75","UNDER":"2.20"},
                "soccer","total:regulation:2.5")
        found=opportunities([a,b],NOW)
        self.assertEqual(len(found),1)
        self.assertEqual({i["outcome"] for i in found[0]["offers"]},{"OVER","UNDER"})
    def test_refuse_total_different_lines_and_settlement(self):
        a=quote("bet365.es",{"OVER":"2.20","UNDER":"1.75"},
                "soccer","total:regulation:2.5")
        b=quote("winamax.es",{"OVER":"1.75","UNDER":"2.20"},
                "soccer","total:regulation:3.5")
        self.assertFalse(opportunities([a,b],NOW))
        self.assertIsNone(market_outcomes("soccer","total:including_ot:2.5"))
        self.assertIsNone(market_outcomes("basketball","total:regulation:224.5"))
    def test_reject_push_line_or_nonstandard_market(self):
        for line in ("total:regulation:3","total:regulation:2.25","total:regulation:-2.5"):
            with self.subTest(line=line):
                with self.assertRaises(BadQuote):
                    quote("bet365.es",{"OVER":"2.2","UNDER":"1.8"},"soccer",line)
    def test_same_event_mild_start_variation_deduplicated(self):
        a=quote("bet365.es",SOCCER_A)
        b=quote("winamax.es",SOCCER_B,start=START+timedelta(seconds=90))
        self.assertEqual(len(opportunities([a,b],NOW)),1)
    def test_individual_book_pairs(self):
        c=quote("codere.es",{"1":"3.40","X":"3.50","2":"1.80"})
        opp=opportunities([quote("bet365.es",SOCCER_A),quote("winamax.es",SOCCER_B),c],NOW)
        self.assertTrue(any(set(x["books"])=={"bet365.es","winamax.es"} for x in opp))
    def test_must_double_check_same_odds(self):
        a=quote("bet365.es",SOCCER_A);b=quote("winamax.es",SOCCER_B)
        original=opportunities([a,b],NOW)
        later=opportunities([a,b],NOW+timedelta(seconds=3))
        self.assertEqual(len(confirm(original,later,NOW,NOW+timedelta(seconds=3))),1)
        changed=quote("winamax.es",{**SOCCER_B,"2":"3.7"})
        changed_opp=opportunities([a,changed],NOW+timedelta(seconds=3))
        self.assertFalse(confirm(original,changed_opp,NOW,NOW+timedelta(seconds=3)))
    def test_reject_same_instant_or_delayed_confirmation(self):
        with self.assertRaises(BadQuote):confirm([],[],NOW,NOW)
        with self.assertRaises(BadQuote):confirm([],[],NOW,NOW+timedelta(minutes=5))
    def test_randomized_stake_rounding_never_claims_false_profit(self):
        rng=random.Random(261022)
        for index in range(200):
            pa={x:str(round(rng.uniform(1.2,7.0),2)) for x in ("1","X","2")}
            pb={x:str(round(rng.uniform(1.2,7.0),2)) for x in ("1","X","2")}
            events=opportunities([
                quote("bet365.es",pa),quote("winamax.es",pb)],NOW)
            for item in events:
                self.assertEqual(sum(Decimal(x["stake"]) for x in item["offers"]),Decimal("100"))
                self.assertGreaterEqual(
                    min(Decimal(x["stake"])*Decimal(x["price"])
                        for x in item["offers"]),Decimal("100.50"))
                self.assertGreater(len(set(x["book"] for x in item["offers"])),1)
    def test_market_anchor_blocks_sport_mismatch(self):
        self.assertIsNone(market_outcomes("tennis","1x2:regulation"))
    def test_deterministic_fingerprint(self):
        a=quote("bet365.es",SOCCER_A);b=quote("winamax.es",SOCCER_B)
        opp=opportunities([a,b],NOW)[0]
        self.assertEqual(fingerprint(opp),fingerprint(opp))
        self.assertTrue(fingerprint(opp).startswith("scrape:"))
    def test_record_schema(self):
        a=quote("bet365.es",SOCCER_A)
        converted=from_record({
            "book":a.book,"sport":a.sport,"home":a.home,"away":a.away,
            "kickoff":a.kickoff.isoformat(),"market":a.market,
            "prices":dict(a.prices),"observed_at":a.observed_at.isoformat(),
            "source":"licensed_feed"})
        self.assertEqual(converted.book,"bet365.es")


class WebParserTests(unittest.TestCase):
    def test_parse_unambiguous_html(self):
        q=parse_html(sample_html(),profile(),NOW)
        self.assertEqual(q.book,"winamax.es")
        self.assertEqual(q.prices["1"],Decimal("3.60"))
        self.assertTrue(q.valid_at(NOW))
    def test_reject_missing_css(self):
        with self.assertRaises(BadQuote):
            parse_html(sample_html().replace('class="odds-draw"','class="x"'),profile(),NOW)
    def test_reject_duplicate_css(self):
        with self.assertRaises(BadQuote):parse_html(sample_html(double=True),profile(),NOW)
    def test_reject_false_price(self):
        with self.assertRaises(BadQuote):parse_html(sample_html(price="2/1"),profile(),NOW)
    def test_market_heading_must_match(self):
        with self.assertRaises(BadQuote):
            parse_html(sample_html().replace("Resultado final","Total de goles"),profile(),NOW)
    def test_market_scope_must_be_unique(self):
        p=profile()
        with self.assertRaises(BadQuote):
            parse_html(sample_html().replace('class="market-box"','class="unexpected"'),p,NOW)
    def test_reject_captcha(self):
        with self.assertRaises(BadQuote):parse_html(sample_html(blocked=True),profile(),NOW)
    def test_reject_not_authorized(self):
        cfg=profile();cfg["permission_confirmed"]=False
        with self.assertRaises(BadQuote):validate_profile(cfg)
    def test_reject_bet365_direct_scrape(self):
        cfg=profile();cfg["book"]="bet365.es";cfg["url"]="https://www.bet365.es/"
        with self.assertRaises(BadQuote):validate_profile(cfg)
    def test_reject_external_url_or_http(self):
        for url in ["https://example.org/x","http://www.winamax.es/x",
                    "https://www.winamax.es.evil.org/x","https://127.0.0.1/private",
                    "https://user:secret@www.winamax.es/x"]:
            cfg=profile();cfg["url"]=url
            with self.subTest(url=url):
                with self.assertRaises(BadQuote):validate_profile(cfg)


class ProviderAdapterTests(unittest.TestCase):
    def test_accepts_complete_active_sport_1x2(self):
        out=convert_fixture(provider_fixture(),NOW)
        self.assertEqual(len(out),2)
        self.assertEqual(out[0].source,"licensed_feed")
        self.assertTrue(opportunities(out,NOW))
    def test_reject_stale_updatedat_in_opportunities(self):
        out=convert_fixture(provider_fixture(updated=NOW-timedelta(hours=10)),NOW)
        self.assertEqual(len(out),2)
        self.assertFalse(opportunities(out,NOW))
    def test_reject_inactive_or_suspended(self):
        f=provider_fixture()
        f["bookmakerOdds"]["bet365.es"]["suspended"]=True
        self.assertEqual(len(convert_fixture(f,NOW)),1)
    def test_reject_incomplete_market(self):
        f=provider_fixture()
        del f["bookmakerOdds"]["bet365.es"]["markets"]["101"]["outcomes"]["102"]
        self.assertEqual(len(convert_fixture(f,NOW)),1)
    def test_two_way_requires_confirmed_settlement(self):
        f=provider_fixture(12)
        self.assertFalse(convert_fixture(f,NOW))
        verified=convert_fixture(f,NOW,{12})
        self.assertEqual(len(verified),2)
    def test_bad_payload_rejected(self):
        with self.assertRaises(BadQuote):convert_fixtures({"data":{}},NOW)

if __name__=="__main__":unittest.main()
