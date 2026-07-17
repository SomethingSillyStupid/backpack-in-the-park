"""CPython preview server for testing the Pico interface over Tailscale."""

import argparse
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import config
from board import Archive, MessageBoard, escape_html, normalize_message, normalize_username, render_messages
from captive_portal import CAPTIVE_PROBE_PATHS, portal_url
from request_policy import request_body_error, urlencoded_body_error

ROOT = os.path.dirname(os.path.abspath(__file__))
RECOVERY_URL = portal_url("192.168.4.1")


def read_request_body(headers, reader):
    """Apply the firmware body policy before the preview allocates or parses."""
    normalized = {name.lower(): value for name, value in headers.items()}
    error = request_body_error(normalized)
    if error is not None:
        return error, None

    length = int(normalized.get("content-length", "0"))
    body = reader.read(length)
    if normalized.get("content-type", "").lower().startswith("application/x-www-form-urlencoded"):
        error = urlencoded_body_error(body, length)
        if error is not None:
            return error, None
    return None, body


def read_template(name):
    with open(os.path.join(ROOT, "static", name), encoding="utf-8") as handle:
        return handle.read()


def replace_tokens(template, values):
    for key, value in values.items():
        template = template.replace("{{%s}}" % key, escape_html(value))
    return template


class PreviewApp:
    def __init__(self, data_dir=None, seed_demo=True):
        self.started = time.monotonic()
        self.data_dir = data_dir or os.path.join(ROOT, "preview-data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.archive = Archive(os.path.join(self.data_dir, "archive.jsonl"), config.MAX_ARCHIVE_BYTES)
        self.board = MessageBoard(config.BOARD_ID, "PREVIEW", self.archive, config.MAX_MESSAGES)
        self.admin_path = config.ADMIN_PATH
        if config.RESTORE_MESSAGES_ON_BOOT:
            self.board.restore_recent(config.RESTORE_MESSAGE_COUNT)
        if seed_demo and not self.board.messages:
            self._seed_demo_messages()

    def now(self):
        return max(0, int(time.monotonic() - self.started))

    def _seed_demo_messages(self):
        samples = [
            ("Anonymous", "Is this thing on?", -42),
            ("MOTH_84", "The network ends here.\nThe conversation does not.", -187),
            ("park_guest", "I came looking for Wi-Fi and found a tiny message board.", -7260),
        ]
        for user, message, posted_at in reversed(samples):
            self.board.messages.insert(0, {"user": user, "message": message, "posted_at": posted_at})

    def render_welcome(self):
        paragraphs = "".join("<p>%s</p>" % escape_html(item) for item in config.WELCOME_PARAGRAPHS)
        image_html = ""
        if config.WELCOME_IMAGE_PATH:
            image_html = '<img class="portrait" src="/welcome-image" alt="%s">' % escape_html(
                config.WELCOME_IMAGE_ALT
            )
        html = replace_tokens(
            read_template("welcome.html"),
            {
                "welcome_title": config.WELCOME_TITLE,
                "welcome_status": config.WELCOME_STATUS,
                "welcome_button_label": config.WELCOME_BUTTON_LABEL,
                "welcome_disclosure": config.WELCOME_DISCLOSURE,
                "recovery_url": RECOVERY_URL,
                "board_name": config.BOARD_NAME,
                "board_id": config.BOARD_ID,
            },
        )
        html = html.replace("{{render_welcome_image()}}", image_html)
        return html.replace("{{render_welcome_paragraphs()}}", paragraphs)

    def render_about(self):
        paragraphs = "".join("<p>%s</p>" % escape_html(item) for item in config.ABOUT_PARAGRAPHS)
        image_html = ""
        if config.WELCOME_IMAGE_PATH:
            image_html = '<img class="portrait" src="/welcome-image" alt="%s">' % escape_html(
                config.WELCOME_IMAGE_ALT
            )
        project_html = ""
        url = config.ABOUT_PROJECT_URL
        if url and (url.startswith("https://") or url.startswith("http://")):
            safe_url = escape_html(url)
            project_html = (
                '<section class="project-link">'
                '<strong>%s</strong>'
                '<span>SAVE THIS ADDRESS FOR LATER:</span>'
                '<a href="%s" rel="external">%s</a>'
                "</section>"
            ) % (escape_html(config.ABOUT_PROJECT_LABEL), safe_url, safe_url)
        html = replace_tokens(
            read_template("about.html"),
            {
                "about_title": config.ABOUT_TITLE,
                "about_status": config.ABOUT_STATUS,
                "about_return_label": config.ABOUT_RETURN_LABEL,
                "recovery_url": RECOVERY_URL,
                "board_name": config.BOARD_NAME,
                "board_id": config.BOARD_ID,
            },
        )
        html = html.replace("{{render_about_image()}}", image_html)
        html = html.replace("{{render_about_paragraphs()}}", paragraphs)
        return html.replace("{{render_about_project_link()}}", project_html)

    def render_public(self, error=""):
        errors = {
            "blank": "Message cannot be blank.",
            "message-long": "Message exceeds 280 characters.",
            "name-long": "User name exceeds 24 characters.",
        }
        error_html = ""
        if error in errors:
            error_html = '<div class="error" role="alert">%s</div>' % escape_html(errors[error])
        html = read_template("index.html")
        html = replace_tokens(
            html,
            {
                "board_name": config.BOARD_NAME,
                "board_id": config.BOARD_ID,
                "recovery_url": RECOVERY_URL,
                "message_count_label": "%d MESSAGE%s"
                % (len(self.board.messages), "" if len(self.board.messages) == 1 else "S"),
            },
        )
        html = html.replace('{{error_html + ""}}', error_html)
        html = html.replace(
            "{{render_messages(messages, now)}}",
            "".join(render_messages(self.board.messages, self.now(), config.RESTORED_TIME_LABEL)),
        )
        return html

    def render_admin(self, message):
        stats = self.archive.stats()
        return replace_tokens(
            read_template("admin.html"),
            {
                "board_name": config.BOARD_NAME,
                "board_id": config.BOARD_ID,
                "boot_id": "PREVIEW",
                "archive_records": str(stats["records"]),
                "archive_bytes": str(stats["bytes"]),
                "admin_path": self.admin_path,
                "admin_message": message,
            },
        )

    def handle(self, method, target, body=b""):
        parsed = urlsplit(target)
        path = parsed.path
        query = parse_qs(parsed.query)
        headers = {"Cache-Control": "no-store"}

        if method == "GET" and path == "/welcome":
            headers["Content-Type"] = "text/html; charset=utf-8"
            return 200, headers, self.render_welcome()

        if method == "GET" and path == "/welcome-image" and config.WELCOME_IMAGE_PATH:
            with open(os.path.join(ROOT, config.WELCOME_IMAGE_PATH), "rb") as handle:
                image = handle.read()
            return 200, {
                "Content-Type": config.WELCOME_IMAGE_MIME,
                "Cache-Control": "public, max-age=3600",
            }, image

        if method == "GET" and path == "/about":
            headers["Content-Type"] = "text/html; charset=utf-8"
            return 200, headers, self.render_about()

        if method == "GET" and path in ("/", "/board"):
            headers["Content-Type"] = "text/html; charset=utf-8"
            return 200, headers, self.render_public(query.get("error", [""])[0])

        if method == "POST" and path == "/post":
            form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            try:
                user = normalize_username(form.get("username", [""])[0], config.MAX_NAME_LENGTH)
                message = normalize_message(form.get("message", [""])[0], config.MAX_MESSAGE_LENGTH)
            except ValueError as error:
                text = str(error)
                code = "name-long" if "Username" in text else "message-long" if "too long" in text else "blank"
                return 303, {"Location": "/?error=" + code}, ""
            self.board.post(user, message, self.now())
            return 303, {"Location": "/"}, ""

        if method == "GET" and path == self.admin_path:
            status = query.get("status", [""])[0]
            message = {
                "deleted": "Archive deleted. The public in-memory board was not changed.",
                "confirm": "Archive not deleted: type DELETE exactly.",
                "delete-failed": "Archive deletion failed. The file may still be present.",
            }.get(status, "Unlinked operator console. This page is not strong authentication.")
            headers["Content-Type"] = "text/html; charset=utf-8"
            return 200, headers, self.render_admin(message)

        if method == "GET" and path == self.admin_path + "/download":
            if self.archive.stats()["records"] == 0:
                return 404, {"Content-Type": "text/plain; charset=utf-8"}, "No archived messages yet."
            with open(self.archive.path, "rb") as handle:
                data = handle.read()
            return 200, {
                "Content-Type": "application/x-ndjson; charset=utf-8",
                "Content-Disposition": 'attachment; filename="%s-archive.jsonl"' % config.BOARD_ID,
                "Cache-Control": "no-store",
            }, data

        if method == "POST" and path == self.admin_path + "/delete":
            form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            confirmation = form.get("confirmation", [""])[0]
            if confirmation == "DELETE":
                status = "deleted" if self.archive.delete() else "delete-failed"
                return 303, {"Location": self.admin_path + "?status=" + status}, ""
            return 303, {"Location": self.admin_path + "?status=confirm"}, ""

        if method == "GET" and path in CAPTIVE_PROBE_PATHS:
            return 302, {"Location": "/"}, ""

        return 302, {"Location": "/"}, ""


class PreviewHandler(BaseHTTPRequestHandler):
    app = None

    def do_GET(self):
        self.respond(*self.app.handle("GET", self.path))

    def do_POST(self):
        error, body = read_request_body(self.headers, self.rfile)
        if error is not None:
            message, status, content_type = error
            self.respond(
                status,
                {"Content-Type": content_type + "; charset=utf-8", "Cache-Control": "no-store"},
                message,
            )
            return
        self.respond(*self.app.handle("POST", self.path, body))

    def respond(self, status, headers, body):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def log_message(self, format, *args):
        return


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def run(host="0.0.0.0", port=8765):
    PreviewHandler.app = PreviewApp()
    server = ReusableThreadingHTTPServer((host, port), PreviewHandler)
    print("Backpack In The Park preview: http://%s:%d" % (host, port), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(args.host, args.port)
