from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "static" / "index.html"
ADMIN_TEMPLATE = ROOT / "static" / "admin.html"
WELCOME_TEMPLATE = ROOT / "static" / "welcome.html"
ABOUT_TEMPLATE = ROOT / "static" / "about.html"


class PublicTemplateTests(unittest.TestCase):
    def setUp(self):
        self.html = TEMPLATE.read_text(encoding="utf-8")

    def test_is_mobile_first_and_self_contained(self):
        self.assertIn('name="viewport"', self.html)
        self.assertNotIn("https://", self.html)
        self.assertNotIn("http://", self.html)
        self.assertIn("<style>", self.html)

    def test_post_form_has_limits_and_counter(self):
        self.assertIn('action="/post"', self.html)
        self.assertIn('name="username"', self.html)
        self.assertIn('maxlength="24"', self.html)
        self.assertIn('name="message"', self.html)
        self.assertIn('maxlength="280"', self.html)
        self.assertIn("0 / 280", self.html)

    def test_manual_refresh_and_disclaimer_are_present(self):
        self.assertIn('href="/board"', self.html)
        self.assertIn('href="/about"', self.html)
        self.assertIn("ABOUT THIS BACKPACK", self.html)
        self.assertIn("REFRESH MESSAGES", self.html)
        self.assertIn("Posts are public and may be archived.", self.html)
        self.assertIn("No device or visitor information is recorded.", self.html)

    def test_dynamic_board_values_and_messages_are_present(self):
        for expression in (
            "{{board_name}}",
            "{{board_id}}",
            "{{message_count_label}}",
            "{{render_messages(messages, now)}}",
        ):
            self.assertIn(expression, self.html)

    def test_uses_retro_visual_language_without_sacrificing_touch_targets(self):
        self.assertIn("#000080", self.html)
        self.assertIn("outset", self.html)
        self.assertIn("min-height: 44px", self.html)

    def test_earlier_session_posts_have_a_dimmed_style(self):
        self.assertIn(".earlier-session", self.html)
        self.assertIn("filter:saturate(.35)", self.html)


class WelcomeTemplateTests(unittest.TestCase):
    def setUp(self):
        self.html = WELCOME_TEMPLATE.read_text(encoding="utf-8")

    def test_welcome_is_local_configurable_and_leads_to_board(self):
        self.assertNotIn("https://", self.html)
        self.assertIn("{{welcome_title}}", self.html)
        self.assertIn("{{render_welcome_image()}}", self.html)
        self.assertIn("{{render_welcome_paragraphs()}}", self.html)
        self.assertIn('href="/board"', self.html)
        self.assertIn("{{welcome_button_label}}", self.html)


class AboutTemplateTests(unittest.TestCase):
    def setUp(self):
        self.html = ABOUT_TEMPLATE.read_text(encoding="utf-8")

    def test_about_is_local_configurable_and_returns_to_board(self):
        self.assertIn('name="viewport"', self.html)
        self.assertNotIn("https://", self.html)
        self.assertIn("{{about_title}}", self.html)
        self.assertIn("{{about_status}}", self.html)
        self.assertIn("{{render_about_image()}}", self.html)
        self.assertIn("{{render_about_paragraphs()}}", self.html)
        self.assertIn("{{render_about_project_link()}}", self.html)
        self.assertIn('href="/board"', self.html)
        self.assertIn("{{about_return_label}}", self.html)

    def test_about_keeps_touch_controls_large(self):
        self.assertIn("min-height: 44px", self.html)


class AdminTemplateTests(unittest.TestCase):
    def setUp(self):
        self.html = ADMIN_TEMPLATE.read_text(encoding="utf-8")

    def test_admin_supports_download_and_explicit_delete_confirmation(self):
        self.assertIn('href="{{admin_path}}/download"', self.html)
        self.assertIn('action="{{admin_path}}/delete"', self.html)
        self.assertIn('name="confirmation"', self.html)
        self.assertIn("Type DELETE", self.html)


if __name__ == "__main__":
    unittest.main()
