"""Checks for manually copied odds; no network, browser or bookmaker session."""
import unittest
from datetime import datetime, timedelta, timezone
from motor_propio.engine import BadQuote, opportunities, from_record
from motor_propio.manual_import import parse_manual_text, records

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
START = (NOW + timedelta(days=1)).isoformat()


def sample(book="bet365.es", prices=("3.60", "3.80", "1.80")):
    return ("[market]\nbook=" + book
            + "\nsport=soccer\nhome=Cambrian United\naway=Airbus UK Broughton"
            + "\nkickoff=" + START + "\nmarket=1x2:regulation"
            + "\n1=" + prices[0] + "\nX=" + prices[1] + "\n2=" + prices[2] + "\n")


class ManualImportTests(unittest.TestCase):
    def test_accept_manual_bet365_without_network(self):
        quoted = parse_manual_text(sample(), NOW)
        self.assertEqual(len(quoted), 1)
        self.assertEqual(quoted[0].source, "manual_observation")
        self.assertEqual(quoted[0].book, "bet365.es")
        self.assertEqual(str(quoted[0].prices["1"]), "3.60")

    def test_accept_copied_spaced_prices_and_comma(self):
        txt = sample().replace("1=3.60", "1 3,60").replace("X=3.80", "X @ 3,80")
        self.assertEqual(str(parse_manual_text(txt, NOW)[0].prices["X"]), "3.80")

    def test_two_manual_sources_produce_candidate(self):
        raw = sample() + "\n" + sample("winamax.es", ("1.80", "3.00", "3.80"))
        quoted = parse_manual_text(raw, NOW)
        self.assertEqual(len(quoted), 2)
        converted = [from_record(r) for r in records(quoted)]
        self.assertTrue(opportunities(converted, NOW))

    def test_reject_duplicate_selection(self):
        with self.assertRaises(BadQuote):
            parse_manual_text(sample().replace("X=3.80", "1=3.10\nX=3.80"), NOW)

    def test_reject_missing_selection(self):
        with self.assertRaises(BadQuote):
            parse_manual_text(sample().replace("X=3.80\n", ""), NOW)

    def test_reject_incompatible_market(self):
        with self.assertRaises(BadQuote):
            parse_manual_text(sample().replace("1x2:regulation", "winner:including_ot"), NOW)

    def test_reject_unknown_and_ambiguous_fields(self):
        with self.assertRaises(BadQuote):
            parse_manual_text(sample() + "secret=foo\n", NOW)

    def test_reject_empty_or_unstructured(self):
        for content in ["", "1 2.10\nX 3.20\n2 2.70", "[market]\n"]:
            with self.subTest(content=content):
                with self.assertRaises(BadQuote):
                    parse_manual_text(content, NOW)

    def test_reject_naive_kickoff(self):
        with self.assertRaises(BadQuote):
            parse_manual_text(sample().replace("+00:00", ""), NOW)

    def test_reject_stale_manual_observation(self):
        q = parse_manual_text(sample(), NOW - timedelta(minutes=5))
        self.assertFalse(q[0].valid_at(NOW))

    def test_reject_fabricated_odds(self):
        with self.assertRaises(BadQuote):
            parse_manual_text(sample().replace("1=3.60", "1=NaN"), NOW)


if __name__ == "__main__":
    unittest.main()
