from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock

from apps.fundamental_analysis import engine, news
from apps.notifications import messages
from apps.trading.pipeline import build_proposal
from tests.test_pipeline import breakout

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def item(title, hours=2, url=None, source="reuters.com"):
    return {"title": title, "url": url or f"https://{source}/{abs(hash(title))}", "source": source,
            "published_at": NOW - timedelta(hours=hours), "provider": "test"}


class NewsTests(TestCase):
    def test_classify(self):
        self.assertEqual(news.classify("Exchange hack: $50M stolen")[0], "negatif")
        self.assertEqual(news.classify("SEC approves spot ETF")[0], "positif")
        self.assertEqual(news.classify("Coin trades sideways")[0], "neutre")
        self.assertEqual(news.classify("Exchange hack: $50M stolen")[1], 3)

    def test_prepare_dedupes_and_drops_old(self):
        raw = [item("Bitcoin ETF approved", 1, "https://a.com/x?utm=1"), item("Bitcoin ETF approved", 2, "https://a.com/x?utm=2"),
               item("Old story", 100), item("Other", 3)]
        out = news.prepare(raw, NOW)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "Bitcoin ETF approved")

    def test_future_dated_dropped(self):
        self.assertEqual(news.prepare([item("x", -5)], NOW), [])

    def test_reliability_and_queries(self):
        self.assertEqual(news.reliability("www.coindesk.com"), "haute")
        self.assertEqual(news.reliability("randomblog.xyz"), "moyenne")
        self.assertEqual(news.query_for("XAUT_USDT"), "gold price")
        self.assertTrue(news.is_gold("XAUT_USDT"))

    def test_gdelt_parsing_and_errors(self):
        s = MagicMock()
        s.get.return_value = MagicMock(status_code=200, json=lambda: {"articles": [
            {"title": " T ", "url": "https://x.com/a", "domain": "x.com", "seendate": "20261116T100000Z"},
            {"title": "bad"}]})
        out = news.fetch_gdelt("BTC_USDT", session=s)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["published_at"].hour, 10)
        s.get.return_value = MagicMock(status_code=500)
        with self.assertRaises(news.NewsError):
            news.fetch_gdelt("BTC_USDT", session=s)


class FundamentalTests(TestCase):
    def test_unavailable_blocks(self):
        r = engine.assess(None, "LONG", NOW, require=True)
        self.assertFalse(r["available"])
        self.assertIn("DONNEES INDISPONIBLES", r["block"])
        self.assertIsNone(engine.assess(None, "LONG", NOW, require=False)["block"])

    def test_no_news_is_available_and_neutral(self):
        r = engine.assess([], "LONG", NOW)
        self.assertEqual((r["available"], r["score"]), (True, 18))  # neutre = la moitie des 35 points

    def test_positive_news_scores_long(self):
        items = news.prepare([item("Spot ETF approved", 1), item("Institutional inflow surge", 2),
                              item("Partnership launch", 3)], NOW)
        r = engine.assess(items, "LONG", NOW)
        self.assertGreater(r["score"], 10)
        self.assertEqual(engine.assess(items, "SHORT", NOW)["score"], 0)

    def test_major_adverse_news_blocks(self):
        items = news.prepare([item("Major exchange hack, funds stolen", 1)], NOW)
        self.assertIn("majeure", engine.assess(items, "LONG", NOW)["block"])
        self.assertIsNone(engine.assess(items, "SHORT", NOW)["block"])

    def test_old_adverse_news_does_not_block(self):
        items = news.prepare([item("Major exchange hack, funds stolen", 30)], NOW)
        self.assertIsNone(engine.assess(items, "LONG", NOW)["block"])


class PipelineNewsTests(TestCase):
    def _news(self, *titles):
        now = datetime.now(timezone.utc)
        raw = [{"title": t, "url": f"https://reuters.com/{i}", "source": "reuters.com",
                "published_at": now - timedelta(hours=1 + i)} for i, t in enumerate(titles)]
        return news.prepare(raw, now)

    def test_news_unavailable_blocks_proposal(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(), {"min_score": 1, "min_confluence": 0}, news=None)
        self.assertEqual(r["status"], "blocked")
        self.assertIn("DONNEES INDISPONIBLES", r["violations"][0])

    def test_adverse_news_blocks(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(), {"min_score": 1, "min_confluence": 0},
                           news=self._news("Exchange hack, funds stolen"))
        self.assertEqual(r["status"], "blocked")

    def test_with_news_proposal_has_fundamental_score(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(), {"min_score": 1, "min_confluence": 0},
                           news=self._news("Spot ETF approved", "Institutional inflow surge", "Partnership launch"))
        self.assertEqual(r["status"], "proposal")
        p = r["proposal"]
        self.assertIsNotNone(p["score_fundamental"])
        self.assertTrue(p["news"])
        self.assertTrue(0 <= p["score_global"] <= 100)
        self.assertTrue(p["confluence"]["partial"])  # sentiment non fourni


class MessageTests(TestCase):
    def test_summary_analysis_digest(self):
        s = messages.format_market_summary([{"symbol": "XAUT_USDT", "price": 2650.5, "change_pct": 0.4,
                                              "direction": "NEUTRE", "score": 0}], "DEMO")
        self.assertIn("XAUT_USDT", s)
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(), {"min_score": 1, "require_news": False, "min_confluence": 0})
        a = messages.format_analysis("BTC_USDT", r["analysis"], r["fundamental"])
        self.assertIn("turtle", a)
        d = messages.format_news_digest([{"symbol": "BTC", "title": "T", "source": "s", "url": "u",
                                          "sentiment": "positif", "importance": 2, "reliability": "haute"}])
        self.assertIn("NOUVELLES", d)


class NewsApiTests(TestCase):
    def _session(self, status=200, payload=None):
        s = MagicMock()
        s.get.return_value = MagicMock(status_code=status, json=lambda: payload)
        return s

    def test_parsing_uses_domain_as_source(self):
        payload = {"status": "ok", "articles": [
            {"title": "Bitcoin ETF approved", "url": "https://www.reuters.com/markets/x", "publishedAt": "2026-11-16T10:00:00Z"},
            {"title": "[Removed]", "url": "https://x.com/a", "publishedAt": "2026-11-16T10:00:00Z"},
            {"title": "No date", "url": "https://x.com/b"}]}
        s = self._session(payload=payload)
        out = news.fetch_newsapi("BTC_USDT", "KEY", session=s, now=NOW)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "www.reuters.com")
        self.assertEqual(news.reliability(out[0]["source"]), "haute")
        self.assertEqual(s.get.call_args.kwargs["headers"], {"X-Api-Key": "KEY"})
        self.assertEqual(s.get.call_args.kwargs["params"]["q"], "bitcoin")

    def test_errors(self):
        with self.assertRaises(news.NewsError):
            news.fetch_newsapi("BTC_USDT", "KEY", session=self._session(429, {"status": "error", "code": "rateLimited", "message": "x"}), now=NOW)
        with self.assertRaises(news.NewsError):
            news.fetch_newsapi("BTC_USDT", "KEY", session=self._session(200, {"status": "error", "code": "apiKeyInvalid"}), now=NOW)

    def test_no_key_no_request(self):
        s = self._session(payload={})
        self.assertEqual(news.fetch_newsapi("BTC_USDT", "", session=s), [])
        s.get.assert_not_called()

    def test_queries(self):
        self.assertEqual(news.newsapi_query("XRP_USDT"), "ripple OR XRP")
        self.assertEqual(news.newsapi_query("XAUT_USDT"), '"gold price" OR "Tether Gold"')
        self.assertEqual(news.newsapi_query("DOGE_USDT"), "dogecoin")
        self.assertEqual(news.newsapi_query("BCH_USDT"), '"bitcoin cash"')

    def test_daily_budget_stops_before_limit(self):
        from datetime import date
        b = news.Budget(2)
        d = date(2026, 11, 18)
        self.assertTrue(b.allow(d)); b.used(); self.assertTrue(b.allow(d)); b.used()
        self.assertFalse(b.allow(d))
        self.assertTrue(b.allow(date(2026, 11, 19)))  # nouveau jour : compteur remis a zero


class NewsDataTests(TestCase):
    def _s(self, status=200, payload=None):
        s = MagicMock()
        s.get.return_value = MagicMock(status_code=status, json=lambda: payload)
        return s

    def test_crypto_endpoint_and_parsing(self):
        payload = {"status": "success", "results": [
            {"title": "Bitcoin ETF approved", "link": "https://www.coindesk.com/a", "pubDate": "2026-11-17 10:00:00"},
            {"title": "", "link": "https://x.com/b", "pubDate": "2026-11-17 10:00:00"},
            {"title": "Bad date", "link": "https://x.com/c", "pubDate": "n/a"}]}
        s = self._s(payload=payload)
        out = news.fetch_newsdata("BTC_USDT", "KEY", session=s)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "www.coindesk.com")
        self.assertEqual(out[0]["published_at"].hour, 10)
        self.assertTrue(s.get.call_args.args[0].endswith("/crypto"))
        self.assertEqual(s.get.call_args.kwargs["params"]["coin"], "btc")

    def test_gold_uses_latest_endpoint(self):
        s = self._s(payload={"status": "success", "results": []})
        news.fetch_newsdata("XAUT_USDT", "KEY", session=s)
        self.assertTrue(s.get.call_args.args[0].endswith("/latest"))

    def test_errors_and_no_key(self):
        with self.assertRaises(news.NewsError):
            news.fetch_newsdata("BTC_USDT", "KEY", session=self._s(401, {"status": "error", "results": {"message": "bad key"}}))
        s = self._s(payload={})
        self.assertEqual(news.fetch_newsdata("BTC_USDT", "", session=s), [])
        s.get.assert_not_called()


class ConfluenceGateTests(TestCase):
    SENT = {"fear_greed": {"value": 15, "label": "Extreme Fear"}, "funding_rate": -0.0008,
            "stats": [{"open_interest_usd": 1e6 + i * 5000, "mark_price": 100 + i * 0.2, "lsr_account": 0.5,
                       "long_liq_usd": 0, "short_liq_usd": 0} for i in range(24)]}

    def _news(self, *titles):
        now = datetime.now(timezone.utc)
        raw = [{"title": t, "url": f"https://reuters.com/{i}", "source": "reuters.com",
                "published_at": now - timedelta(hours=1 + i)} for i, t in enumerate(titles)]
        return news.prepare(raw, now)

    def test_default_threshold_blocks_weak_confluence(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(), {"min_score": 1, "require_news": False})
        self.assertEqual(r["status"], "none")
        self.assertIn("confluence", r["reason"])

    def test_aligned_news_and_sentiment_give_strong_proposal(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(), {"min_score": 1},
                           news=self._news("Spot ETF approved", "Institutional inflow surge", "Partnership launch"),
                           sentiment=self.SENT)
        self.assertEqual(r["status"], "proposal")
        c = r["proposal"]["confluence"]
        self.assertFalse(c["partial"])
        self.assertGreaterEqual(c["score"], 65)
        self.assertIn("CONFLUENCE", messages.format_proposal({**r["proposal"], "id": 1, "expires_at": "-"}))

    def test_sentiment_required_but_missing_blocks(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(),
                           {"min_score": 1, "require_news": False, "require_sentiment": True, "min_confluence": 0})
        self.assertEqual(r["status"], "blocked")
        self.assertIn("sentiment", r["violations"][0])
