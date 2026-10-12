import tempfile
import unittest
from pathlib import Path
from datetime import date
from unittest.mock import Mock, patch
from spring_boot_selection.discovery import search_page, collect_range, PopulationStore, WindowCheckpoint
from spring_boot_selection.util import load_config

class DiscoverySafetyTests(unittest.TestCase):
    def test_http_error_is_not_an_empty_population(self):
        client = Mock()
        client.rest_get.return_value.status_code = 503
        with self.assertRaises(RuntimeError):
            search_page(client, "topic:spring-boot fork:true", 1)

    def test_incomplete_search_is_rejected(self):
        client = Mock()
        client.rest_get.return_value.status_code = 200
        client.rest_get.return_value.json.return_value = {"total_count": 12, "items": [], "incomplete_results": True}
        with self.assertRaises(RuntimeError):
            search_page(client, "topic:spring-boot fork:true", 1)

    def test_short_page_does_not_complete_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PopulationStore(root / "population.csv")
            checkpoint = WindowCheckpoint(root / "windows.json")
            with patch("spring_boot_selection.discovery.search_page", side_effect=[(2, [{"id": 1, "full_name": "a/b"}], False), (2, [], False)]):
                with self.assertRaises(RuntimeError):
                    collect_range(Mock(), store, checkpoint, root / "queries.csv", load_config(), date(2020,1,1), date(2020,1,2))
            self.assertEqual(checkpoint.done, set())
            self.assertEqual(store.seen, {"1"})

    def test_overflow_is_not_silently_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = WindowCheckpoint(root / "windows.json")
            with patch("spring_boot_selection.discovery.search_page", return_value=(1001, [], False)):
                with self.assertRaises(RuntimeError):
                    collect_range(Mock(), PopulationStore(root / "population.csv"), checkpoint, root / "queries.csv", load_config(), date(2020,1,1), date(2020,1,1), "0..0")
            self.assertEqual(checkpoint.done, set())

class SnapshotReferenceTests(unittest.TestCase):
    def test_filter_reuses_snapshot_date_instead_of_today(self):
        import csv
        import json
        from argparse import Namespace
        from spring_boot_selection.cli import cmd_filter
        from spring_boot_selection.util import DEFAULT_CONFIG
        from tests.test_spring_boot_selection import repo
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = repo(pushed_at="2023-10-01T00:00:00Z")
            with (root / "population.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            (root / "count.json").write_text(json.dumps({"collected_at": "2026-09-17T16:36:06Z", "total_count": 1}))
            args = Namespace(config=DEFAULT_CONFIG, run_dir=root, limit=50000)
            with patch("spring_boot_selection.filters.utc_now", side_effect=AssertionError("wall clock must not change the cutoff")):
                self.assertEqual(cmd_filter(args), 0)
            metadata = json.loads((root / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["cutoff_date"], "2023-09-17T16:36:06Z")
            self.assertEqual(metadata["selected_count"], 1)
