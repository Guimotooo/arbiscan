import unittest
from datetime import datetime, timezone
from fuentes_es.direct_bwin import parse_bwin_time, parse_cards


NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


class Tests(unittest.TestCase):
    def test_visible_dom_card_becomes_a_provenanced_quote(self):
        cards = [{"href": "/es/sports/eventos/celtic-celta-2:123",
                  "teams": ["Celtic", "Celta de Vigo"], "start": "Mañana / 21:00",
                  "market": "Resultado del Partido", "labels": ["1", "X", "2"],
                  "prices": ["2.60", "3.60", "2.45"]}]
        quotes = parse_cards(cards, NOW)
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].book, "bwin.es")
        self.assertEqual(str(quotes[0].prices["X"]), "3.60")
        self.assertEqual(quotes[0].source, "permitted_web")

    def test_ambiguous_or_wrong_market_is_ignored(self):
        cards = [{"href": "/es/sports/eventos/a-b-2:1", "teams": ["A", "B"],
                  "start": "Mañana / 21:00", "market": "Total de goles",
                  "labels": ["1", "X", "2"], "prices": ["2", "3", "4"]},
                 {"href": "/es/sports/eventos/a-b-2:2", "teams": ["A", "B"],
                  "start": "viernes / 21:00", "market": "Resultado del Partido",
                  "labels": ["1", "X", "2"], "prices": ["2", "3", "4"]}]
        self.assertEqual(parse_cards(cards, NOW), [])

    def test_only_unambiguous_relative_dates_are_parsed(self):
        self.assertIsNotNone(parse_bwin_time("Hoy / 14:00", NOW))
        self.assertIsNotNone(parse_bwin_time("Mañana / 14:00", NOW))
        self.assertIsNone(parse_bwin_time("viernes / 14:00", NOW))
        self.assertIsNone(parse_bwin_time("Hoy / 99:00", NOW))


if __name__ == "__main__":
    unittest.main()
