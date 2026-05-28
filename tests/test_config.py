from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_gpu_lens.config import parse_gpu_prices, parse_simple_yaml


class ConfigTest(unittest.TestCase):
    def test_parse_simple_yaml_mapping(self) -> None:
        config = parse_simple_yaml(
            """
            language: zh
            hours: 168
            gpu_prices:
              default: 2.5
              H100: 4.25
            """
        )

        self.assertEqual(config["language"], "zh")
        self.assertEqual(config["hours"], 168)
        self.assertEqual(config["gpu_prices"]["default"], 2.5)
        self.assertEqual(config["gpu_prices"]["H100"], 4.25)

    def test_parse_gpu_prices(self) -> None:
        prices = parse_gpu_prices(["H100=4.25", "L40S=1.35"])

        self.assertEqual(prices, {"H100": 4.25, "L40S": 1.35})


if __name__ == "__main__":
    unittest.main()
