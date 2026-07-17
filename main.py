"""Backpack In The Park firmware for Raspberry Pi Pico W + MicroPython + Phew."""

import os
import time

from phew import access_point, dns, logging, server
from phew.server import FileResponse, Response, redirect
from phew.template import render_template

import config
from board import (
    Archive,
    MessageBoard,
    decode_form_value,
    escape_html,
    next_boot_id,
    normalize_message,
    normalize_username,
    render_messages,
)

# Privacy contract: Phew logs request paths to flash by default. Replace every
# logging entry point so both bundled and older Phew variants remain silent.
def no_log(*items):
    return None


for name in ("log", "info", "warn", "error", "debug", "exception"):
    setattr(logging, name, no_log)
try:
    os.remove("log.txt")
except OSError:
    pass

BOOT_STARTED = time.time()
BOOT_ID = next_boot_id(config.BOOT_ID_PATH)
archive = Archive(config.ARCHIVE_PATH, config.MAX_ARCHIVE_BYTES)
board = MessageBoard(config.BOARD_ID, BOOT_ID, archive, config.MAX_MESSAGES)
if config.RESTORE_MESSAGES_ON_BOOT:
    board.restore_recent(config.RESTORE_MESSAGE_COUNT)


def uptime_seconds():
    return max(0, int(time.time() - BOOT_STARTED))


def error_markup(code):
    messages = {
        "blank": "Message cannot be blank.",
        "message-long": "Message exceeds 280 characters.",
        "name-long": "User name exceeds 24 characters.",
    }
    message = messages.get(code)
    if not message:
        return ""
    return '<div class="error" role="alert">%s</div>' % escape_html(message)


def html_response(body):
    return Response(
        body,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store",
        },
    )


def render_welcome_paragraphs():
    for paragraph in config.WELCOME_PARAGRAPHS:
        yield "<p>%s</p>" % escape_html(paragraph)


def render_welcome_image():
    if config.WELCOME_IMAGE_PATH:
        yield '<img class="portrait" src="/welcome-image" alt="%s">' % escape_html(
            config.WELCOME_IMAGE_ALT
        )


def render_about_paragraphs():
    for paragraph in config.ABOUT_PARAGRAPHS:
        yield "<p>%s</p>" % escape_html(paragraph)


def render_about_image():
    if config.WELCOME_IMAGE_PATH:
        yield '<img class="portrait" src="/welcome-image" alt="%s">' % escape_html(
            config.WELCOME_IMAGE_ALT
        )


def render_about_project_link():
    url = config.ABOUT_PROJECT_URL
    if not url or not (url.startswith("https://") or url.startswith("http://")):
        return
    safe_url = escape_html(url)
    yield (
        '<section class="project-link">'
        '<strong>%s</strong>'
        '<span>SAVE THIS ADDRESS FOR LATER:</span>'
        '<a href="%s" rel="external">%s</a>'
        "</section>"
    ) % (escape_html(config.ABOUT_PROJECT_LABEL), safe_url, safe_url)


def render_board_messages(messages, now):
    return render_messages(messages, now, restored_label=config.RESTORED_TIME_LABEL)


@server.route("/", methods=["GET"])
def welcome(request):
    return html_response(render_template(
        "static/welcome.html",
        welcome_title=config.WELCOME_TITLE,
        welcome_status=config.WELCOME_STATUS,
        welcome_button_label=config.WELCOME_BUTTON_LABEL,
        welcome_disclosure=config.WELCOME_DISCLOSURE,
        board_name=config.BOARD_NAME,
        board_id=config.BOARD_ID,
        render_welcome_paragraphs=render_welcome_paragraphs,
        render_welcome_image=render_welcome_image,
    ))


@server.route("/welcome-image", methods=["GET"])
def welcome_image(request):
    if not config.WELCOME_IMAGE_PATH:
        return "No welcome image configured.", 404, "text/plain"
    return FileResponse(
        config.WELCOME_IMAGE_PATH,
        headers={
            "Content-Type": config.WELCOME_IMAGE_MIME,
            "Cache-Control": "public, max-age=3600",
        },
    )


@server.route("/about", methods=["GET"])
def about(request):
    return html_response(render_template(
        "static/about.html",
        about_title=config.ABOUT_TITLE,
        about_status=config.ABOUT_STATUS,
        about_return_label=config.ABOUT_RETURN_LABEL,
        board_name=config.BOARD_NAME,
        board_id=config.BOARD_ID,
        render_about_paragraphs=render_about_paragraphs,
        render_about_image=render_about_image,
        render_about_project_link=render_about_project_link,
    ))


@server.route("/board", methods=["GET"])
def index(request):
    return html_response(render_template(
        "static/index.html",
        board_name=config.BOARD_NAME,
        board_id=config.BOARD_ID,
        message_count_label=(
            "%d MESSAGE%s" % (len(board.messages), "" if len(board.messages) == 1 else "S")
        ),
        messages=board.messages,
        now=uptime_seconds(),
        render_messages=render_board_messages,
        error_html=error_markup(request.query.get("error", "")),
    ))


@server.route("/post", methods=["POST"])
def post_message(request):
    try:
        raw_user = decode_form_value(request.form.get("username", ""))
        raw_message = decode_form_value(request.form.get("message", ""))
        user = normalize_username(raw_user, config.MAX_NAME_LENGTH)
        message = normalize_message(raw_message, config.MAX_MESSAGE_LENGTH)
    except ValueError as error:
        text = str(error)
        if "Username" in text:
            code = "name-long"
        elif "too long" in text:
            code = "message-long"
        else:
            code = "blank"
        return redirect("/board?error=" + code, 303)

    board.post(user, message, uptime_seconds())
    return redirect("/board", 303)


def admin_status_message(request):
    status = request.query.get("status", "")
    if status == "deleted":
        return "Archive deleted. The public in-memory board was not changed."
    if status == "confirm":
        return "Archive not deleted: type DELETE exactly."
    if status == "delete-failed":
        return "Archive deletion failed. The file may still be present."
    return "Unlinked operator console. This page is not strong authentication."


@server.route(config.ADMIN_PATH, methods=["GET"])
def admin(request):
    stats = archive.stats()
    return html_response(render_template(
        "static/admin.html",
        board_name=config.BOARD_NAME,
        board_id=config.BOARD_ID,
        boot_id=str(BOOT_ID),
        archive_records=str(stats["records"]),
        archive_bytes=str(stats["bytes"]),
        admin_path=config.ADMIN_PATH,
        admin_message=admin_status_message(request),
    ))


@server.route(config.ADMIN_PATH + "/download", methods=["GET"])
def download_archive(request):
    if archive.stats()["records"] == 0:
        return "No archived messages yet.", 404, "text/plain"
    filename = "%s-archive.jsonl" % config.BOARD_ID
    return FileResponse(
        config.ARCHIVE_PATH,
        headers={
            "Content-Type": "application/x-ndjson; charset=utf-8",
            "Content-Disposition": 'attachment; filename="%s"' % filename,
            "Cache-Control": "no-store",
        },
    )


@server.route(config.ADMIN_PATH + "/delete", methods=["POST"])
def delete_archive(request):
    confirmation = request.form.get("confirmation", "")
    if confirmation == "DELETE":
        if archive.delete():
            return redirect(config.ADMIN_PATH + "?status=deleted", 303)
        return redirect(config.ADMIN_PATH + "?status=delete-failed", 303)
    return redirect(config.ADMIN_PATH + "?status=confirm", 303)


# Captive portal probes and unknown HTTP destinations return to the board.
@server.catchall()
def catchall(request):
    return redirect("http://%s/board" % ap_ip, 302)


# Open AP: no password, internet uplink, registration, or login.
ap = access_point(config.SSID)
ap_ip = ap.ifconfig()[0]
dns.run_catchall(ap_ip)
server.run()
