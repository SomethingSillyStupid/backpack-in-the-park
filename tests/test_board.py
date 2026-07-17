import json
import os
import tempfile
import unittest
from unittest.mock import patch

from board import (
    Archive,
    MessageBoard,
    age_label,
    escape_html,
    decode_form_value,
    next_boot_id,
    normalize_message,
    normalize_username,
    render_messages,
)


class TextValidationTests(unittest.TestCase):
    def test_blank_username_becomes_anonymous(self):
        self.assertEqual(normalize_username("  \n "), "Anonymous")

    def test_username_is_trimmed_and_limited(self):
        self.assertEqual(normalize_username("  Alice  ", 24), "Alice")
        with self.assertRaises(ValueError):
            normalize_username("x" * 25, 24)

    def test_message_keeps_line_breaks_and_rejects_blank_text(self):
        self.assertEqual(normalize_message("  hello\r\nwoods  "), "hello\nwoods")
        with self.assertRaises(ValueError):
            normalize_message(" \r\n\t ")

    def test_message_enforces_unicode_character_limit(self):
        self.assertEqual(normalize_message("🌲" * 280), "🌲" * 280)
        with self.assertRaises(ValueError):
            normalize_message("🌲" * 281)

    def test_phew_percent_decoded_utf8_is_recovered(self):
        # Phew currently converts each percent-encoded byte with chr().
        phew_value = "ð\u009f\u008c\u00b2 hello"
        self.assertEqual(decode_form_value(phew_value), "🌲 hello")

    def test_html_is_escaped(self):
        self.assertEqual(
            escape_html("<script>'x' & \"y\"</script>"),
            "&lt;script&gt;&#39;x&#39; &amp; &quot;y&quot;&lt;/script&gt;",
        )


class TimeDisplayTests(unittest.TestCase):
    def test_age_labels(self):
        cases = [
            (0, "just now"),
            (59, "just now"),
            (60, "1 minute ago"),
            (119, "1 minute ago"),
            (120, "2 minutes ago"),
            (3600, "1 hour ago"),
            (7200, "2 hours ago"),
            (86400, "1 day ago"),
            (172800, "2 days ago"),
        ]
        for seconds, expected in cases:
            with self.subTest(seconds=seconds):
                self.assertEqual(age_label(seconds), expected)


class ArchiveAndBoardTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.archive_path = os.path.join(self.tempdir.name, "archive.jsonl")
        self.archive = Archive(self.archive_path, max_bytes=100_000)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_recent_archive_records_restore_newest_first_without_reappending(self):
        for number in range(1, 5):
            self.archive.append(
                {
                    "board": "BITP-001",
                    "boot": number,
                    "posted_at": number * 10,
                    "user": "Visitor %d" % number,
                    "message": "message %d" % number,
                }
            )
        board = MessageBoard("BITP-001", 99, self.archive, max_messages=3)
        restored = board.restore_recent(2)
        self.assertEqual(restored, 2)
        self.assertEqual([item["message"] for item in board.messages], ["message 4", "message 3"])
        self.assertTrue(all(item["restored"] for item in board.messages))
        self.assertEqual(self.archive.stats()["records"], 4)

    def test_post_is_visible_newest_first_and_archived(self):
        board = MessageBoard("SITP-001", 7, self.archive, max_messages=2)
        board.post("Alice", "first", 10)
        board.post("Bob", "second", 20)
        board.post("Cat", "third", 30)

        self.assertEqual([item["message"] for item in board.messages], ["third", "second"])
        with open(self.archive_path, encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle]
        self.assertEqual(len(records), 3)
        self.assertEqual(
            records[-1],
            {
                "board": "SITP-001",
                "boot": 7,
                "posted_at": 30,
                "user": "Cat",
                "message": "third",
            },
        )

    def test_archive_failure_does_not_prevent_ephemeral_post(self):
        archive = Archive(self.archive_path, max_bytes=1)
        board = MessageBoard("SITP-001", 1, archive, max_messages=10)
        archived = board.post("Anonymous", "still visible", 1)
        self.assertFalse(archived)
        self.assertEqual(board.messages[0]["message"], "still visible")

    def test_archive_stats_and_delete(self):
        board = MessageBoard("SITP-001", 1, self.archive, max_messages=10)
        board.post("A", "one", 1)
        board.post("B", "two", 2)
        stats = self.archive.stats()
        self.assertEqual(stats["records"], 2)
        self.assertGreater(stats["bytes"], 0)
        self.assertTrue(self.archive.delete())
        self.assertEqual(self.archive.stats(), {"records": 0, "bytes": 0})

    def test_rendered_messages_escape_content_and_preserve_newlines(self):
        messages = [{"user": "<b>A</b>", "message": "one\n<script>x</script>", "posted_at": 10}]
        html = "".join(render_messages(messages, now=70))
        self.assertIn("&lt;b&gt;A&lt;/b&gt;", html)
        self.assertIn("one<br>&lt;script&gt;x&lt;/script&gt;", html)
        self.assertIn("1 minute ago", html)
        self.assertNotIn("<script>", html)

    def test_restored_message_is_dimmed_and_has_honest_session_label(self):
        messages = [
            {
                "user": "Moth",
                "message": "still here",
                "posted_at": 10,
                "restored": True,
            }
        ]
        html = "".join(render_messages(messages, now=9999, restored_label="EARLIER SESSION"))
        self.assertIn('class="message-card earlier-session"', html)
        self.assertIn("EARLIER SESSION", html)
        self.assertNotIn("ago", html)

    def test_empty_board_has_period_appropriate_message(self):
        html = "".join(render_messages([], now=0))
        self.assertIn("NO MESSAGES FOUND", html)

    def test_boot_id_increments_across_starts(self):
        path = os.path.join(self.tempdir.name, "boot.id")
        self.assertEqual(next_boot_id(path), 1)
        self.assertEqual(next_boot_id(path), 2)

    def test_boot_id_recovers_completed_temporary_update(self):
        path = os.path.join(self.tempdir.name, "boot.id")
        with open(path, "w") as handle:
            handle.write("4")
        with open(path + ".tmp", "w") as handle:
            handle.write("5")
        self.assertEqual(next_boot_id(path), 6)

    def test_boot_id_keeps_highest_slot_when_next_write_loses_power(self):
        path = os.path.join(self.tempdir.name, "boot.id")
        with open(path + ".tmp", "w") as handle:
            handle.write("5")
        real_open = open

        def interrupted_open(candidate, mode="r", *args, **kwargs):
            if mode == "w" and candidate in (path, path + ".tmp"):
                handle = real_open(candidate, mode, *args, **kwargs)
                handle.close()
                raise OSError("simulated power loss after truncation")
            return real_open(candidate, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=interrupted_open):
            with self.assertRaises(OSError):
                next_boot_id(path)
        self.assertEqual(next_boot_id(path), 6)

    def test_archive_repairs_partial_final_record_after_power_loss(self):
        with open(self.archive_path, "wb") as handle:
            handle.write(b'{"message":"good"}\n{"message":"interrupted')
        recovered = Archive(self.archive_path, max_bytes=100_000)
        self.assertTrue(recovered.append({"message": "next"}))
        with open(self.archive_path, encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(records, [{"message": "good"}, {"message": "next"}])


if __name__ == "__main__":
    unittest.main()
