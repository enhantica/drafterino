import unittest

from src.drafterino.main import bump_version
from src.drafterino.main import generate_release_notes
from src.drafterino.main import substitute_placeholders


class TestVersionBump(unittest.TestCase):
    def test_patch_bump(self):
        self.assertEqual(bump_version("1.2.3", "patch"), "1.2.4")

    def test_minor_bump(self):
        self.assertEqual(bump_version("1.2.3", "minor"), "1.3.0")

    def test_major_bump(self):
        self.assertEqual(bump_version("1.2.3", "major"), "2.0.0")

    def test_post_bump_initial(self):
        self.assertEqual(bump_version("1.2.3", "post"), "1.2.3.post1")

    def test_post_bump_increment(self):
        self.assertEqual(bump_version("1.2.3.post2", "post"), "1.2.3.post3")


class TestPlaceholderSubstitution(unittest.TestCase):
    def test_substitute_placeholders(self):
        cfg = {
            "tag": "v$COMPUTED_VERSION",
            "title": "Release $COMPUTED_VERSION"
        }
        substitute_placeholders(cfg, "1.0.0")
        self.assertEqual(cfg["tag"], "v1.0.0")
        self.assertEqual(cfg["title"], "Release 1.0.0")


class TestReleaseNotes(unittest.TestCase):
    def test_generate_release_notes(self):
        prs = [
            {"title": "Fix bug", "number": 1, "labels": [{"name": "[scope] bug"}]},
            {"title": "Improve docs", "number": 2, "labels": [{"name": "[scope] documentation"}]},
        ]
        cfg = {
            "release-notes": [
                {"title": "Fixed", "labels": ["[scope] bug"]},
                {"title": "Docs", "labels": ["[scope] documentation"]}
            ]
        }
        notes = generate_release_notes(prs, cfg)
        expected = (
            "## Fixed\n- Fix bug (#1)\n\n"
            "## Docs\n- Improve docs (#2)"
        )
        self.assertEqual(notes.strip(), expected.strip())


if __name__ == "__main__":
    unittest.main()