from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.snapshot_cache_helper import SnapshotCache


class SnapshotCacheHelperTests(unittest.TestCase):
    def test_get_or_load_reuses_cached_value_until_invalidated(self) -> None:
        cache: SnapshotCache[list[str]] = SnapshotCache()
        calls: list[int] = []

        def loader() -> list[str]:
            calls.append(1)
            return ["demo"]

        self.assertFalse(cache.has_value)
        self.assertEqual(cache.get_or_load(loader), ["demo"])
        self.assertTrue(cache.has_value)
        self.assertEqual(cache.get_or_load(loader), ["demo"])
        self.assertEqual(len(calls), 1)

        cache.invalidate()

        self.assertFalse(cache.has_value)
        self.assertEqual(cache.get_or_load(loader), ["demo"])
        self.assertEqual(len(calls), 2)

    def test_get_or_load_keeps_empty_list_cached(self) -> None:
        cache: SnapshotCache[list[str]] = SnapshotCache()
        calls: list[int] = []

        def loader() -> list[str]:
            calls.append(1)
            return []

        self.assertEqual(cache.get_or_load(loader), [])
        self.assertEqual(cache.get_or_load(loader), [])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
