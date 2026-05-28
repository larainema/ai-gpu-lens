from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_gpu_lens import prometheus
from ai_gpu_lens.model import Series


class QueryRangeFallbackTest(unittest.TestCase):
    def test_empty_primary_uses_fallback_query(self) -> None:
        calls: list[str] = []
        original_query_range = prometheus.query_range

        def fake_query_range(
            prometheus_url: str,
            query: str,
            start: datetime,
            end: datetime,
            step: str,
            timeout: float = 20.0,
            basic_auth: tuple[str, str] | None = None,
            bearer_token: str | None = None,
        ) -> tuple[Series, ...]:
            calls.append(query)
            if query == "primary":
                return ()
            return (Series(metric={"source": "fallback"}, values=((0, 1),)),)

        try:
            prometheus.query_range = fake_query_range
            result = prometheus.query_range_with_fallback(
                "http://prometheus.example.com",
                "primary",
                "fallback",
                datetime.fromtimestamp(0, timezone.utc),
                datetime.fromtimestamp(60, timezone.utc),
                "1m",
            )
        finally:
            prometheus.query_range = original_query_range

        self.assertEqual(calls, ["primary", "fallback"])
        self.assertEqual(result[0].metric["source"], "fallback")

    def test_primary_result_skips_fallback_query(self) -> None:
        calls: list[str] = []
        original_query_range = prometheus.query_range

        def fake_query_range(
            prometheus_url: str,
            query: str,
            start: datetime,
            end: datetime,
            step: str,
            timeout: float = 20.0,
            basic_auth: tuple[str, str] | None = None,
            bearer_token: str | None = None,
        ) -> tuple[Series, ...]:
            calls.append(query)
            return (Series(metric={"source": query}, values=((0, 1),)),)

        try:
            prometheus.query_range = fake_query_range
            result = prometheus.query_range_with_fallback(
                "http://prometheus.example.com",
                "primary",
                "fallback",
                datetime.fromtimestamp(0, timezone.utc),
                datetime.fromtimestamp(60, timezone.utc),
                "1m",
            )
        finally:
            prometheus.query_range = original_query_range

        self.assertEqual(calls, ["primary"])
        self.assertEqual(result[0].metric["source"], "primary")


if __name__ == "__main__":
    unittest.main()
