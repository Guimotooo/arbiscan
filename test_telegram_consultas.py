import unittest
from decimal import Decimal
from telegram_consultas import parse_message, evaluate, render

class ArbiTests(unittest.TestCase):
    def test_two_way(self):
        p = parse_message('/comparar\nDeporte: futbol\nPartido: A vs B\nMercado: total goles 2.5 (90 minutos)\nCapital: 100\nBet365 ES | mas | 2.10\nSportium ES | menos | 2.05')
        r = evaluate(p)
        self.assertIsNotNone(r)
        self.assertGreater(r[1]["profit"], Decimal("3.5"))
        self.assertIn("NO VERIFICADAS",render(p,r))
    def test_three_way(self):
        p = parse_message('/comparar\nDeporte: futbol\nPartido: A vs B\nMercado: 1X2 (90 minutos)\nCapital: 100\nBet365 ES | 1 | 3.8\nSportium ES | X | 3.8\nWinamax ES | 2 | 3.8')
        self.assertIsNotNone(evaluate(p))
    def test_missing_outcome(self):
        p = parse_message('/comparar\nDeporte: futbol\nPartido: A vs B\nMercado: 1X2 (90 minutos)\nCapital: 100\nBet365 ES | 1 | 2.5\nSportium ES | X | 2.5')
        with self.assertRaisesRegex(ValueError,"Falta cubrir"):
            evaluate(p)
    def test_no_arbitrage(self):
        p = parse_message('/comparar\nDeporte: futbol\nPartido: A vs B\nMercado: 1X2 (90 minutos)\nCapital: 100\nBet365 ES | 1 | 1.5\nSportium ES | X | 3.5\nWinamax ES | 2 | 4')
        self.assertIsNone(evaluate(p))
    def test_push_rejected(self):
        with self.assertRaisesRegex(ValueError,".5"):
            parse_message('/comparar\nDeporte: futbol\nPartido: A vs B\nMercado: total goles 3 (90 minutos)\nCapital: 100\nBet365 ES | mas | 2.1\nSportium ES | menos | 2.05')
    def test_soccer_two_way_rejected(self):
        with self.assertRaisesRegex(ValueError,"1X2"):
            parse_message('/comparar\nDeporte: futbol\nPartido: A vs B\nMercado: ganador\nCapital: 100\nBet365 ES | 1 | 2.1\nSportium ES | 2 | 2.05')
    def test_nba_overtime(self):
        with self.assertRaisesRegex(ValueError,"prórroga"):
            parse_message('/comparar\nDeporte: nba\nPartido: A vs B\nMercado: total puntos 220.5\nCapital: 100\nBet365 ES | mas | 2.1\nSportium ES | menos | 2.05')
    def test_one_house_only(self):
        p = parse_message('/comparar\nDeporte: futbol\nPartido: A vs B\nMercado: total goles 2.5 (90 minutos)\nCapital: 100\nBet365 ES | mas | 2.1\nBet365 ES | menos | 2.05')
        self.assertIsNone(evaluate(p))

if __name__ == "__main__":
    unittest.main()
