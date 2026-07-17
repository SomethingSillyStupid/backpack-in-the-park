"""Per-installation settings. Edit these before copying files to a Pico W."""

# Keep SSID at or below 32 UTF-8 bytes. Include the direct recovery IP so a
# visitor can rediscover the board from Wi-Fi settings after closing the tab.
SSID = "BACKPACK-001 OPEN 192.168.4.1"
BOARD_NAME = "BACKPACK IN THE PARK"
BOARD_ID = "BITP-001"

# Captive introduction. Text is escaped; use plain text rather than HTML.
WELCOME_TITLE = "BACKPACK IN THE PARK"
WELCOME_STATUS = "YOU HAVE DISCOVERED A LOCAL NETWORK"
WELCOME_PARAGRAPHS = (
    "This small network lives only within range of this object.",
    "It has no connection to the internet. Read what earlier visitors left behind, or leave something of your own.",
)
WELCOME_BUTTON_LABEL = "ENTER MESSAGE BOARD"
WELCOME_DISCLOSURE = (
    "Messages are public and may be archived for future art projects. "
    "No device or visitor information is recorded."
)

# Optional local portrait for this unit. Set to None for a text-only welcome.
# JPEG is recommended: roughly 320–800 px and under 150 KiB.
WELCOME_IMAGE_PATH = "static/welcome.svg"
WELCOME_IMAGE_MIME = "image/svg+xml"
WELCOME_IMAGE_ALT = "A small Backpack In The Park field unit"

# About page shown after someone has visited the board. Keep this useful while
# offline: the project address is displayed for the visitor to save for later.
ABOUT_TITLE = "ABOUT THIS BACKPACK"
ABOUT_STATUS = "LOCAL ARTIFACT // NO INTERNET REQUIRED"
ABOUT_PARAGRAPHS = (
    "Backpack In The Park is a tiny, place-bound message board running entirely on a Raspberry Pi Pico W.",
    "It creates its own local network, remembers the latest messages across restarts, and records no visitor or device information.",
    "This unit can have its own name, portrait, and story. If you found it in the park, you have already become part of that story.",
)
ABOUT_PROJECT_LABEL = "PROJECT NOTES / BUILD YOUR OWN"
ABOUT_PROJECT_URL = "https://github.com/SomethingSillyStupid/backpack-in-the-park"
ABOUT_RETURN_LABEL = "RETURN TO MESSAGE BOARD"

# This is intentionally unlinked, not authenticated. Make it unique per unit.
ADMIN_PATH = "/operator-copper-moth-7f29d1"

MAX_MESSAGES = 50
MAX_NAME_LENGTH = 24
MAX_MESSAGE_LENGTH = 280
MAX_ARCHIVE_BYTES = 512 * 1024

RESTORE_MESSAGES_ON_BOOT = True
RESTORE_MESSAGE_COUNT = 20
RESTORED_TIME_LABEL = "EARLIER SESSION"

ARCHIVE_PATH = "archive.jsonl"
BOOT_ID_PATH = "boot.id"
