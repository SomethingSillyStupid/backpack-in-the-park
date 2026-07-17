import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from preview_server import PreviewApp


class PreviewAppTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.app = PreviewApp(data_dir=self.tempdir.name, seed_demo=False)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_root_is_configurable_welcome_and_board_is_separate(self):
        status, headers, body = self.app.handle("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertNotIn("{{", body)
        self.assertIn("ENTER MESSAGE BOARD", body)
        self.assertIn('href="/board"', body)

        status, _, body = self.app.handle("GET", "/board")
        self.assertEqual(status, 200)
        self.assertNotIn("{{", body)
        self.assertIn("NO MESSAGES FOUND", body)

    def test_welcome_image_is_served_locally(self):
        status, headers, body = self.app.handle("GET", "/welcome-image")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertIsInstance(body, bytes)
        self.assertIn(b"<svg", body)

    def test_about_page_is_configurable_escaped_and_returns_to_board(self):
        with (
            patch("config.ABOUT_TITLE", "About <this>"),
            patch("config.ABOUT_PARAGRAPHS", ("Unit <script>alert(1)</script>",)),
        ):
            status, headers, body = self.app.handle("GET", "/about")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertNotIn("{{", body)
        self.assertIn("About &lt;this&gt;", body)
        self.assertIn("Unit &lt;script&gt;alert(1)&lt;/script&gt;", body)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn('href="/board"', body)
        self.assertIn("RETURN TO MESSAGE BOARD", body)

    def test_about_project_url_rejects_unsafe_scheme(self):
        with patch("config.ABOUT_PROJECT_URL", "javascript:alert(1)"):
            _, _, body = self.app.handle("GET", "/about")
        self.assertNotIn("javascript:", body)

    def test_post_redirects_and_appears_on_page(self):
        payload = urlencode({"username": "Moth", "message": "one\ntwo"}).encode()
        status, headers, _ = self.app.handle("POST", "/post", payload)
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/board")
        _, _, body = self.app.handle("GET", "/board")
        self.assertIn("Moth", body)
        self.assertIn("one<br>two", body)
        self.assertIn("1 MESSAGE", body)
        self.assertNotIn("1 MESSAGES", body)

    def test_unknown_path_redirects_to_board(self):
        status, headers, _ = self.app.handle("GET", "/generate_204")
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "/board")

    def test_new_preview_instance_restores_archived_posts_as_earlier_session(self):
        payload = urlencode({"username": "Cache", "message": "remember this"}).encode()
        self.app.handle("POST", "/post", payload)
        restarted = PreviewApp(data_dir=self.tempdir.name, seed_demo=False)
        _, _, body = restarted.handle("GET", "/board")
        self.assertIn("remember this", body)
        self.assertIn("EARLIER SESSION", body)
        self.assertIn("earlier-session", body)

    def test_admin_download_and_delete_flow(self):
        payload = urlencode({"username": "A", "message": "saved"}).encode()
        self.app.handle("POST", "/post", payload)
        status, headers, body = self.app.handle("GET", self.app.admin_path + "/download")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn(b'"message": "saved"', body)

        wrong = urlencode({"confirmation": "delete"}).encode()
        status, _, _ = self.app.handle("POST", self.app.admin_path + "/delete", wrong)
        self.assertEqual(status, 303)
        self.assertTrue(os.path.exists(self.app.archive.path))

        correct = urlencode({"confirmation": "DELETE"}).encode()
        self.app.handle("POST", self.app.admin_path + "/delete", correct)
        self.assertFalse(os.path.exists(self.app.archive.path))


if __name__ == "__main__":
    unittest.main()
