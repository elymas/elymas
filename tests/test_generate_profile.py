from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from datetime import date

from scripts import generate_profile as profile


class GenerateProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = profile.load_config(profile.DEFAULT_CONFIG)
        display = cls.config["display"]
        cls.template = profile.project_path(display["template_path"]).read_text(encoding="utf-8")
        cls.portrait = profile.project_path(display["portrait_path"]).read_text(encoding="utf-8")
        cls.stats = {
            "repositories": 17,
            "stars": 43,
            "followers": 11,
            "github_years": 9,
            "top_repository": "ai_chatbot_class",
            "top_repository_stars": 41,
            "refreshed_on": "2026-08-14 KST",
        }

    def test_github_years_respects_anniversary(self) -> None:
        created_at = "2017-08-12T17:19:13Z"
        self.assertEqual(profile.github_years(created_at, date(2026, 8, 11)), 8)
        self.assertEqual(profile.github_years(created_at, date(2026, 8, 12)), 9)

    def test_top_repository_ignores_forks_and_archives(self) -> None:
        repositories = [
            {"name": "fork", "stargazers_count": 100, "fork": True, "archived": False},
            {"name": "archive", "stargazers_count": 90, "fork": False, "archived": True},
            {"name": "active", "stargazers_count": 7, "fork": False, "archived": False},
        ]
        self.assertEqual(profile.pick_top_repository(repositories)["name"], "active")

    def test_both_themes_render_as_valid_svg(self) -> None:
        for theme in profile.THEMES.values():
            rendered = profile.render_svg(
                self.template, theme, self.config, self.stats, self.portrait
            )
            root = ET.fromstring(rendered)
            self.assertTrue(root.tag.endswith("svg"))
            self.assertNotRegex(rendered, profile.PLACEHOLDER_PATTERN)
            self.assertIn("ai_chatbot_class", rendered)
            self.assertIn("elymas@gmail.com", rendered)

    def test_ascii_text_is_xml_escaped(self) -> None:
        tspans = profile.ascii_tspans("<&")
        self.assertIn("&lt;&amp;", tspans)


if __name__ == "__main__":
    unittest.main()
