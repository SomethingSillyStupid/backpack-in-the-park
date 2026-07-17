"""Small, testable transport policy used by the vendored Phew server."""

MAX_BODY_BYTES = 4096
HEX_DIGITS = "0123456789abcdefABCDEF"


def request_body_error(headers):
    """Return a Phew response tuple when a request body must be rejected."""
    content_type = headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        return "Multipart forms are not accepted", 415, "text/plain"

    if "content-length" not in headers:
        return None
    try:
        content_length = int(headers["content-length"])
    except (ValueError, TypeError):
        return "Bad Content-Length", 400, "text/plain"
    if content_length < 0:
        return "Bad Content-Length", 400, "text/plain"
    if content_length > MAX_BODY_BYTES:
        return "Payload too large", 413, "text/plain"
    return None


def urlencoded_body_error(body, expected_length):
    """Reject truncated or malformed URL-encoded input before form parsing."""
    if len(body) != expected_length:
        return "Incomplete request body", 400, "text/plain"
    try:
        text = body.decode("utf-8")
    except (UnicodeError, AttributeError):
        return "Malformed form body", 400, "text/plain"

    for parameter in text.split("&"):
        if "=" not in parameter:
            return "Malformed form body", 400, "text/plain"
        position = 0
        while True:
            position = parameter.find("%", position)
            if position == -1:
                break
            if position + 2 >= len(parameter):
                return "Malformed form body", 400, "text/plain"
            if parameter[position + 1] not in HEX_DIGITS or parameter[position + 2] not in HEX_DIGITS:
                return "Malformed form body", 400, "text/plain"
            position += 3
    return None
