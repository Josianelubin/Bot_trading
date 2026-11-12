from unittest import TestCase

from apps.risk_management.discipline import check_plan

OK_STATE = {"equity_usdt": 1000, "daily_loss_pct": 0, "consecutive_losses": 0, "minutes_since_last_loss": None}
PLAN = {"direction": "LONG", "entry": 100.0, "stop_loss": 99.0, "take_profit": 102.0,
        "capital_usdt": 50, "leverage": 10}  # risque 50*10*1% = 5 USDT = 0.5 %


class DisciplineTests(TestCase):
    def test_valid_plan(self):
        self.assertTrue(check_plan(PLAN, OK_STATE)["allowed"])

    def test_missing_stop(self):
        r = check_plan({**PLAN, "stop_loss": None}, OK_STATE)
        self.assertFalse(r["allowed"])

    def test_wrong_side_stop(self):
        self.assertFalse(check_plan({**PLAN, "stop_loss": 101.0}, OK_STATE)["allowed"])

    def test_risk_too_high(self):
        r = check_plan({**PLAN, "capital_usdt": 500}, OK_STATE)
        self.assertTrue(any("equite" in x for x in r["violations"]))

    def test_low_reward_risk(self):
        r = check_plan({**PLAN, "take_profit": 100.5}, OK_STATE)
        self.assertTrue(any("gain/risque" in x for x in r["violations"]))

    def test_stop_near_liquidation(self):
        r = check_plan({**PLAN, "stop_loss": 91.0, "take_profit": 120.0, "capital_usdt": 5, "leverage": 10}, OK_STATE)
        self.assertTrue(any("liquidation" in x for x in r["violations"]))

    def test_daily_loss_blocks(self):
        self.assertFalse(check_plan(PLAN, {**OK_STATE, "daily_loss_pct": 3.5})["allowed"])

    def test_consecutive_losses_block(self):
        self.assertFalse(check_plan(PLAN, {**OK_STATE, "consecutive_losses": 3})["allowed"])

    def test_revenge_trading_cooldown(self):
        r = check_plan(PLAN, {**OK_STATE, "minutes_since_last_loss": 5})
        self.assertTrue(any("revenge" in x for x in r["violations"]))
