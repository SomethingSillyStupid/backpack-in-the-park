"""Captive-portal routing and bounded DNS response helpers."""

CAPTIVE_PROBE_PATHS = (
    "/hotspot-detect.html",
    "/library/test/success.html",
    "/generate_204",
    "/gen_204",
    "/connecttest.txt",
    "/ncsi.txt",
    "/canonical.html",
    "/success.txt",
)


def portal_url(ap_ip):
    return "http://%s/" % ap_ip


def configure_ap_dns(access_point):
    """Make DHCP clients use the local catch-all DNS server."""
    configuration = access_point.ifconfig()
    ap_ip = configuration[0]
    if configuration[3] != ap_ip:
        access_point.ifconfig(configuration[:3] + (ap_ip,))
    return ap_ip


def _hostname(host_header):
    host = (host_header or "").strip().lower()
    if host.startswith("["):
        closing = host.find("]")
        return host[1:closing] if closing != -1 else host
    return host.split(":", 1)[0]


def external_host_redirect(headers, ap_ip):
    """Return the canonical portal URL for intercepted foreign HTTP hosts."""
    host = _hostname(headers.get("host", ""))
    if not host or host == str(ap_ip).strip().lower():
        return None
    return portal_url(ap_ip)


def _question_end(request):
    if len(request) < 17 or request[4:6] != b"\x00\x01":
        return None
    cursor = 12
    while cursor < len(request):
        label_length = request[cursor]
        cursor += 1
        if label_length == 0:
            break
        if label_length > 63 or cursor + label_length > len(request):
            return None
        cursor += label_length
    else:
        return None
    if cursor + 4 > len(request):
        return None
    return cursor + 4


def _valid_additional_section(request, question_end):
    additional_count = (request[10] << 8) | request[11]
    if additional_count == 0:
        return question_end == len(request)
    if additional_count != 1 or question_end + 11 > len(request):
        return False

    # Accept one structurally valid EDNS OPT pseudo-record and ignore it.
    if request[question_end] != 0 or request[question_end + 1 : question_end + 3] != b"\x00\x29":
        return False
    data_length = (request[question_end + 9] << 8) | request[question_end + 10]
    return question_end + 11 + data_length == len(request)


def build_dns_response(request, ip_address):
    """Answer standard A queries locally and return clean NODATA otherwise."""
    question_end = _question_end(request)
    if question_end is None:
        return None

    flags = (request[2] << 8) | request[3]
    if flags & 0xF800 or request[6:10] != b"\x00\x00\x00\x00":
        return None
    if not _valid_additional_section(request, question_end):
        return None

    query_type = (request[question_end - 4] << 8) | request[question_end - 3]
    query_class = (request[question_end - 2] << 8) | request[question_end - 1]
    answer_count = b"\x00\x01" if query_type == 1 and query_class == 1 else b"\x00\x00"
    response_flags = 0x8000 | (flags & 0x0100)
    response = (
        request[:2]
        + bytes((response_flags >> 8, response_flags & 0xFF))
        + b"\x00\x01"
        + answer_count
        + b"\x00\x00\x00\x00"
        + request[12:question_end]
    )
    if answer_count == b"\x00\x00":
        return response

    try:
        address = bytes(map(int, ip_address.split(".")))
    except (TypeError, ValueError):
        return None
    if len(address) != 4:
        return None
    return response + b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + address
