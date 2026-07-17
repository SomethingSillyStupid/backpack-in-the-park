import unittest

from captive_portal import (
    CAPTIVE_PROBE_PATHS,
    build_dns_response,
    configure_ap_dns,
    external_host_redirect,
    portal_url,
)


class FakeAccessPoint:
    def __init__(self, configuration):
        self.configuration = configuration
        self.updated = None

    def ifconfig(self, value=None):
        if value is not None:
            self.updated = value
            self.configuration = value
        return self.configuration


def dns_query(query_type, flags=b"\x01\x00", qd=1, an=0, ns=0, ar=0, suffix=b""):
    labels = b"\x07example\x03com\x00"
    counts = bytes((0, qd, 0, an, 0, ns, 0, ar))
    return (
        b"\x12\x34"
        + flags
        + counts
        + labels
        + bytes((query_type >> 8, query_type & 0xFF, 0, 1))
        + suffix
    )


class CaptivePortalRoutingTests(unittest.TestCase):
    def test_external_http_hosts_redirect_to_canonical_local_root(self):
        self.assertEqual(
            external_host_redirect({"host": "example.com"}, "192.168.4.1"),
            "http://192.168.4.1/",
        )
        self.assertEqual(
            external_host_redirect({"host": "93.184.216.34:80"}, "192.168.4.1"),
            "http://192.168.4.1/",
        )

    def test_local_ip_host_keeps_canonical_page(self):
        self.assertIsNone(external_host_redirect({"host": "192.168.4.1"}, "192.168.4.1"))
        self.assertIsNone(external_host_redirect({"host": "192.168.4.1:80"}, "192.168.4.1"))
        self.assertIsNone(external_host_redirect({}, "192.168.4.1"))

    def test_portal_url_is_absolute_http_root(self):
        self.assertEqual(portal_url("192.168.4.1"), "http://192.168.4.1/")

    def test_common_os_captive_probe_paths_are_explicit(self):
        for path in (
            "/hotspot-detect.html",
            "/library/test/success.html",
            "/generate_204",
            "/gen_204",
            "/connecttest.txt",
            "/ncsi.txt",
            "/canonical.html",
            "/success.txt",
        ):
            self.assertIn(path, CAPTIVE_PROBE_PATHS)

    def test_ap_advertises_its_own_dns_address(self):
        ap = FakeAccessPoint(("192.168.4.1", "255.255.255.0", "192.168.4.1", "0.0.0.0"))
        self.assertEqual(configure_ap_dns(ap), "192.168.4.1")
        self.assertEqual(
            ap.updated,
            ("192.168.4.1", "255.255.255.0", "192.168.4.1", "192.168.4.1"),
        )

    def test_ap_dns_configuration_is_not_rewritten_when_already_local(self):
        configuration = ("192.168.4.1", "255.255.255.0", "192.168.4.1", "192.168.4.1")
        ap = FakeAccessPoint(configuration)
        self.assertEqual(configure_ap_dns(ap), "192.168.4.1")
        self.assertIsNone(ap.updated)


class CaptiveDnsTests(unittest.TestCase):
    def test_ipv4_query_gets_local_a_answer(self):
        request = dns_query(1)
        response = build_dns_response(request, "192.168.4.1")
        self.assertEqual(response[:2], request[:2])
        self.assertEqual(response[2:4], b"\x81\x00")
        self.assertEqual(response[4:6], b"\x00\x01")
        self.assertEqual(response[6:8], b"\x00\x01")
        self.assertEqual(response[12 : len(request)], request[12:])
        self.assertTrue(response.endswith(b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04\xc0\xa8\x04\x01"))

    def test_ipv6_and_https_queries_get_clean_no_data_answers(self):
        for query_type in (28, 65):
            with self.subTest(query_type=query_type):
                request = dns_query(query_type)
                response = build_dns_response(request, "192.168.4.1")
                self.assertEqual(response[4:6], b"\x00\x01")
                self.assertEqual(response[6:8], b"\x00\x00")
                self.assertEqual(response[12:], request[12:])
                self.assertNotIn(b"\xc0\xa8\x04\x01", response)

    def test_malformed_or_multi_question_queries_are_ignored(self):
        self.assertIsNone(build_dns_response(b"short", "192.168.4.1"))
        multi = bytearray(dns_query(1))
        multi[5] = 2
        self.assertIsNone(build_dns_response(bytes(multi), "192.168.4.1"))
        truncated = dns_query(1)[:-2]
        self.assertIsNone(build_dns_response(truncated, "192.168.4.1"))

    def test_non_query_flags_counts_and_trailing_bytes_are_rejected(self):
        for request in (
            dns_query(1, flags=b"\x81\x00"),
            dns_query(1, flags=b"\x09\x00"),
            dns_query(1, an=1),
            dns_query(1, ns=1),
            dns_query(1, suffix=b"garbage"),
            dns_query(1, ar=1),
        ):
            with self.subTest(request=request):
                self.assertIsNone(build_dns_response(request, "192.168.4.1"))

    def test_valid_edns_opt_is_accepted_but_not_echoed(self):
        opt = b"\x00\x00\x29\x04\xd0\x00\x00\x00\x00\x00\x00"
        response = build_dns_response(dns_query(1, ar=1, suffix=opt), "192.168.4.1")
        self.assertIsNotNone(response)
        self.assertEqual(response[2:4], b"\x81\x00")
        self.assertEqual(response[10:12], b"\x00\x00")
        self.assertTrue(response.endswith(b"\xc0\xa8\x04\x01"))

    def test_compressed_question_name_is_rejected(self):
        request = dns_query(1).replace(b"\x07example\x03com\x00", b"\xc0\x0c", 1)
        self.assertIsNone(build_dns_response(request, "192.168.4.1"))


if __name__ == "__main__":
    unittest.main()
