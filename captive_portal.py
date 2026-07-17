"""Host-aware captive-portal routing shared by firmware tests."""


def board_url(ap_ip):
    return "http://%s/board" % ap_ip


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
    """Return the board URL for intercepted HTTP requests to foreign hosts."""
    host = _hostname(headers.get("host", ""))
    if not host or host == str(ap_ip).strip().lower():
        return None
    return board_url(ap_ip)
