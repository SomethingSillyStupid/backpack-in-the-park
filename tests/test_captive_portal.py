import unittest

from captive_portal import board_url, configure_ap_dns, external_host_redirect


class FakeAccessPoint:
    def __init__(self, configuration):
        self.configuration = configuration
        self.updated = None

    def ifconfig(self, value=None):
        if value is not None:
            self.updated = value
            self.configuration = value
        return self.configuration


class CaptivePortalRoutingTests(unittest.TestCase):
    def test_external_http_hosts_redirect_to_local_board(self):
        self.assertEqual(
            external_host_redirect({"host": "example.com"}, "192.168.4.1"),
            "http://192.168.4.1/board",
        )
        self.assertEqual(
            external_host_redirect({"host": "93.184.216.34:80"}, "192.168.4.1"),
            "http://192.168.4.1/board",
        )

    def test_local_ip_host_keeps_the_captive_introduction(self):
        self.assertIsNone(external_host_redirect({"host": "192.168.4.1"}, "192.168.4.1"))
        self.assertIsNone(external_host_redirect({"host": "192.168.4.1:80"}, "192.168.4.1"))
        self.assertIsNone(external_host_redirect({}, "192.168.4.1"))

    def test_board_url_is_absolute_http(self):
        self.assertEqual(board_url("192.168.4.1"), "http://192.168.4.1/board")

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


if __name__ == "__main__":
    unittest.main()
