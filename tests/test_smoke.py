"""Smoke tests: package imports and version."""

from __future__ import annotations

import unittest


class TestPackageSmoke(unittest.TestCase):
    def test_version_defined(self) -> None:
        import traffic_study

        self.assertTrue(isinstance(traffic_study.__version__, str))
        self.assertTrue(len(traffic_study.__version__) > 0)

    def test_parsers_import(self) -> None:
        from traffic_study.parsers import parse_int

        self.assertIsNone(parse_int(""))
        self.assertEqual(parse_int("42"), 42)


if __name__ == "__main__":
    unittest.main()
