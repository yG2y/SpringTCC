from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spring_boot_selection.discovery import build_discovery_query, normalize_repo
from spring_boot_selection.filters import classify_non_software, run_filters, sort_eligible
from spring_boot_selection.util import load_config, minus_years


def repo(**overrides):
    base = {
        "repository_id": 1,
        "full_name": "acme/app",
        "html_url": "https://github.com/acme/app",
        "description": "Production service",
        "is_fork": False,
        "is_mirror": False,
        "mirror_url": "",
        "is_template": False,
        "archived": False,
        "disabled": False,
        "default_branch": "main",
        "size_kb": 120,
        "language": "Java",
        "stargazers_count": 10,
        "forks_count": 1,
        "topics": "spring-boot",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "pushed_at": "2026-06-01T00:00:00Z",
        "license": "MIT",
    }
    base.update(overrides)
    return base


class DiscoveryQueryTests(unittest.TestCase):
    def test_includes_forks_and_omits_language(self):
        query = build_discovery_query("topic:spring-boot", True, "2012-01-01..2012-12-31")
        self.assertEqual(query, "topic:spring-boot fork:true created:2012-01-01..2012-12-31")
        self.assertNotIn("language:", query)

    def test_normalize_keeps_forks_and_non_java(self):
        item = {
            "id": 99,
            "full_name": "acme/forked",
            "html_url": "https://github.com/acme/forked",
            "description": "x",
            "fork": True,
            "language": "TypeScript",
            "stargazers_count": 3,
            "topics": ["spring-boot"],
            "archived": False,
            "size": 10,
            "default_branch": "main",
            "created_at": "2020-01-01T00:00:00Z",
            "pushed_at": "2020-01-02T00:00:00Z",
            "updated_at": "2020-01-03T00:00:00Z",
            "license": {"spdx_id": "MIT"},
        }
        row = normalize_repo(item, "part")
        self.assertIsNotNone(row)
        self.assertTrue(row["is_fork"])
        self.assertEqual(row["language"], "TypeScript")


class FilterPipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.now = datetime(2026, 9, 16, tzinfo=timezone.utc)

    def test_attrition_and_reasons(self):
        rows = [
            repo(repository_id=1, full_name="a/prod", stargazers_count=50),
            repo(repository_id=2, full_name="a/fork", is_fork=True, stargazers_count=40),
            repo(repository_id=3, full_name="a/mirror", mirror_url="https://example.com", stargazers_count=30),
            repo(repository_id=4, full_name="a/old", archived=True, stargazers_count=20),
            repo(repository_id=5, full_name="a/off", disabled=True, stargazers_count=20),
            repo(
                repository_id=6,
                full_name="a/stale",
                pushed_at="2020-01-01T00:00:00Z",
                stargazers_count=20,
            ),
            repo(repository_id=7, full_name="a/tmpl", is_template=True, stargazers_count=20),
            repo(repository_id=8, full_name="a/empty", size_kb=0, default_branch="", stargazers_count=20),
            repo(
                repository_id=9,
                full_name="school/java-course",
                topics="spring-boot; tutorial",
                stargazers_count=15,
            ),
            repo(
                repository_id=10,
                full_name="org/spring-boot-demo",
                description="demo app",
                stargazers_count=5,
            ),
            repo(
                repository_id=11,
                full_name="org/kotlin-api",
                language="Kotlin",
                stargazers_count=8,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_filters(rows, self.config, Path(tmp), collection_time=self.now)
        attrition = {row["stage"]: row for row in result["attrition"]}
        self.assertEqual(attrition["universe"]["input_count"], 11)
        self.assertEqual(attrition["remove_primary_language"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_forks"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_mirrors"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_archived"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_disabled"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_inactive"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_templates"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_empty"]["excluded_count"], 1)
        self.assertEqual(attrition["remove_non_software"]["excluded_count"], 1)
        names = {row["full_name"] for row in result["eligible"]}
        self.assertEqual(names, {"a/prod", "org/spring-boot-demo"})
        self.assertEqual(result["flagged_non_software"], 1)
        self.assertIn("tutorial", result["non_software_reason_counts"])

    def test_primary_language_exact_match_missing_and_alias(self):
        rows = [repo(repository_id=1, language="Java"),
                repo(repository_id=2, language="JavaScript"),
                repo(repository_id=3, language=None),
                repo(repository_id=4, language="Kotlin"),
                repo(repository_id=5, language="java"),
                repo(repository_id=6, language="Java", primary_language="Kotlin")]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_filters(rows, self.config, Path(tmp), collection_time=self.now)
        self.assertEqual({r["repository_id"] for r in result["eligible"]}, {1, 5})
        self.assertEqual(result["attrition"][1]["excluded_count"], 4)
        self.assertTrue(all(r["primary_language"].lower() == "java" for r in result["eligible"]))

    def test_language_filter_can_be_disabled(self):
        self.config["primary_language"] = None
        with tempfile.TemporaryDirectory() as tmp:
            result = run_filters([repo(language="Kotlin")], self.config, Path(tmp), collection_time=self.now)
        self.assertEqual(len(result["eligible"]), 1)
        self.assertNotIn("remove_primary_language", [s["stage"] for s in result["attrition"]])

    def test_example_in_name_is_flagged_not_excluded(self):
        auto, flagged = classify_non_software(
            repo(full_name="org/spring-boot-examples", topics="spring-boot"),
            self.config["non_software"],
        )
        self.assertEqual(auto, [])
        self.assertTrue(any("example" in item for item in flagged))

    def test_sort_is_deterministic(self):
        rows = [
            repo(repository_id=3, stargazers_count=10, pushed_at="2026-01-01T00:00:00Z"),
            repo(repository_id=1, stargazers_count=10, pushed_at="2026-01-01T00:00:00Z"),
            repo(repository_id=2, stargazers_count=20, pushed_at="2025-01-01T00:00:00Z"),
        ]
        ordered = sort_eligible(rows, self.config["ordering"])
        self.assertEqual([row["repository_id"] for row in ordered], [2, 1, 3])
        self.assertEqual(
            [row["repository_id"] for row in ordered],
            [row["repository_id"] for row in sort_eligible(list(reversed(rows)), self.config["ordering"])],
        )

    def test_cutoff_is_dynamic(self):
        cutoff = minus_years(self.now, 3)
        self.assertEqual(cutoff.year, 2023)


if __name__ == "__main__":
    unittest.main()
