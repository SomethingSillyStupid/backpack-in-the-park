"""Core message-board behavior shared by the Pico firmware and local preview.

This module deliberately has no networking dependencies so it can be tested with
ordinary CPython before being copied to a Raspberry Pi Pico W.
"""

try:
    import ujson as json
except ImportError:  # CPython test/preview environment
    import json

import os


DEFAULT_MAX_NAME_LENGTH = 24
DEFAULT_MAX_MESSAGE_LENGTH = 280


def decode_form_value(value):
    """Repair UTF-8 percent-decoding performed byte-by-byte by Phew."""
    value = value or ""
    try:
        if all(ord(character) <= 255 for character in value):
            return bytes(ord(character) for character in value).decode("utf-8")
    except (UnicodeError, ValueError):
        pass
    return value


def normalize_username(value, max_length=DEFAULT_MAX_NAME_LENGTH):
    value = (value or "").strip()
    if not value:
        return "Anonymous"
    if len(value) > max_length:
        raise ValueError("Username is too long.")
    return value


def normalize_message(value, max_length=DEFAULT_MAX_MESSAGE_LENGTH):
    value = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        raise ValueError("Message cannot be blank.")
    if len(value) > max_length:
        raise ValueError("Message is too long.")
    return value


def escape_html(value):
    """Escape submitted text before placing it in an HTML response."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
        .replace(">", "&gt;")
        .replace("<", "&lt;")
    )


def age_label(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return "%d minute%s ago" % (minutes, "" if minutes == 1 else "s")
    hours = minutes // 60
    if hours < 24:
        return "%d hour%s ago" % (hours, "" if hours == 1 else "s")
    days = hours // 24
    return "%d day%s ago" % (days, "" if days == 1 else "s")


def render_messages(messages, now, restored_label="EARLIER SESSION"):
    """Yield safe HTML in small chunks to reduce peak RAM use on the Pico."""
    if not messages:
        yield '<div class="empty-state">*** NO MESSAGES FOUND ***</div>'
        return

    for message in messages:
        user = escape_html(message["user"])
        text = escape_html(message["message"]).replace("\n", "<br>")
        restored = bool(message.get("restored", False))
        age = escape_html(restored_label if restored else age_label(now - message["posted_at"]))
        css_class = "message-card earlier-session" if restored else "message-card"
        yield (
            '<article class="%s">'
            '<header><strong>%s</strong><span>%s</span></header>'
            '<div class="message-text">%s</div>'
            "</article>"
        ) % (css_class, user, age, text)


def next_boot_id(path="boot.id"):
    """Increment using two alternating slots so one valid value always survives."""
    slots = (path, path + ".tmp")
    values = {}
    for candidate in slots:
        try:
            with open(candidate, "r") as handle:
                values[candidate] = int(handle.read().strip() or "0")
        except (OSError, ValueError):
            pass

    boot_id = (max(values.values()) if values else 0) + 1
    if not values:
        target = path
    elif len(values) == 1:
        target = slots[1] if slots[0] in values else slots[0]
    else:
        target = min(slots, key=lambda candidate: values[candidate])

    # Only overwrite the lower/missing slot. If power fails during this write,
    # the other slot still contains the previous highest completed boot ID.
    with open(target, "w") as handle:
        handle.write(str(boot_id))
    return boot_id


class Archive:
    """Append-only JSON Lines archive with a hard size ceiling."""

    def __init__(self, path="archive.jsonl", max_bytes=512 * 1024):
        self.path = path
        self.max_bytes = max_bytes
        self._recover_interrupted_swap()
        self._repair_partial_tail()

    def _exists(self, path):
        try:
            os.stat(path)
            return True
        except OSError:
            return False

    def _recover_interrupted_swap(self):
        repair = self.path + ".repair"
        backup = self.path + ".backup"
        if not self._exists(self.path) and self._exists(backup):
            os.rename(backup, self.path)
        elif self._exists(self.path) and self._exists(backup):
            os.remove(backup)
        if self._exists(repair):
            os.remove(repair)

    def _repair_partial_tail(self):
        size = self._size()
        if size == 0:
            return
        with open(self.path, "rb") as source:
            source.seek(size - 1)
            if source.read(1) == b"\n":
                return

            valid_end = 0
            position = size
            while position > 0:
                start = max(0, position - 256)
                source.seek(start)
                chunk = source.read(position - start)
                newline = chunk.rfind(b"\n")
                if newline != -1:
                    valid_end = start + newline + 1
                    break
                position = start

        repair = self.path + ".repair"
        backup = self.path + ".backup"
        with open(self.path, "rb") as source, open(repair, "wb") as target:
            remaining = valid_end
            while remaining:
                chunk = source.read(min(512, remaining))
                if not chunk:
                    break
                target.write(chunk)
                remaining -= len(chunk)

        os.rename(self.path, backup)
        try:
            os.rename(repair, self.path)
        except OSError:
            os.rename(backup, self.path)
            raise
        os.remove(backup)

    def _size(self):
        try:
            return os.stat(self.path)[6]
        except OSError:
            return 0

    def append(self, record):
        encoded = json.dumps(record) + "\n"
        encoded_size = len(encoded.encode("utf-8"))
        if self._size() + encoded_size > self.max_bytes:
            return False
        try:
            with open(self.path, "a") as handle:
                handle.write(encoded)
            return True
        except OSError:
            return False

    def recent(self, limit, board_id=None):
        """Return the latest valid records using memory proportional to limit."""
        limit = max(0, int(limit))
        if not limit:
            return []
        records = []
        try:
            with open(self.path, "r") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                        if board_id is not None and record.get("board") != board_id:
                            continue
                        if not isinstance(record.get("user"), str) or not isinstance(record.get("message"), str):
                            continue
                        int(record.get("posted_at", 0))
                    except (ValueError, TypeError, AttributeError):
                        continue
                    records.append(record)
                    if len(records) > limit:
                        records.pop(0)
        except OSError:
            return []
        return records

    def stats(self):
        try:
            size = os.stat(self.path)[6]
            records = 0
            with open(self.path, "r") as handle:
                for line in handle:
                    if line.strip():
                        records += 1
            return {"records": records, "bytes": size}
        except OSError:
            return {"records": 0, "bytes": 0}

    def delete(self):
        try:
            os.remove(self.path)
            return True
        except OSError:
            return False


class MessageBoard:
    """Bounded, newest-first public view backed by an append-only archive."""

    def __init__(self, board_id, boot_id, archive, max_messages=50):
        self.board_id = board_id
        self.boot_id = boot_id
        self.archive = archive
        self.max_messages = max_messages
        self.messages = []

    def restore_recent(self, limit):
        records = self.archive.recent(min(limit, self.max_messages), self.board_id)
        self.messages = []
        for record in reversed(records):
            self.messages.append(
                {
                    "user": record["user"],
                    "message": record["message"],
                    "posted_at": int(record.get("posted_at", 0)),
                    "restored": True,
                }
            )
        return len(self.messages)

    def post(self, user, message, posted_at):
        item = {
            "user": user,
            "message": message,
            "posted_at": int(posted_at),
            "restored": False,
        }
        self.messages.insert(0, item)
        if len(self.messages) > self.max_messages:
            self.messages.pop()

        record = {
            "board": self.board_id,
            "boot": self.boot_id,
            "posted_at": int(posted_at),
            "user": user,
            "message": message,
        }
        return self.archive.append(record)
