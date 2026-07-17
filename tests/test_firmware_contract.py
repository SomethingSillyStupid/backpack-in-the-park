from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FirmwareContractTests(unittest.TestCase):
    def test_main_configures_open_ap_dns_and_host_aware_catchall(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("ap = access_point(config.SSID)", source)
        self.assertIn("ap_ip = configure_ap_dns(ap)", source)
        self.assertIn("dns.run_catchall(ap_ip)", source)
        self.assertIn("@server.catchall()", source)
        self.assertIn("external_host_redirect(request.headers, ap_ip)", source)
        self.assertIn("def local_only(handler):", source)
        self.assertEqual(source.count("@local_only"), 8)
        self.assertIn("return redirect(destination, 302)", source)
        self.assertIn("return redirect(portal_url(ap_ip), 302)", source)
        self.assertIn("for path in CAPTIVE_PROBE_PATHS:", source)
        self.assertIn('server.add_route(path, captive_probe, methods=["GET"])', source)

    def test_dns_transport_uses_query_type_aware_response_builder(self):
        source = (ROOT / "phew" / "dns.py").read_text(encoding="utf-8")
        self.assertIn("from captive_portal import build_dns_response", source)
        self.assertIn("response = build_dns_response(request, ip_address)", source)
        self.assertIn("if response is not None:", source)

    def test_main_has_public_post_and_hidden_admin_routes(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('@server.route("/", methods=["GET"])', source)
        self.assertIn('@server.route("/board", methods=["GET"])', source)
        self.assertIn('@server.route("/welcome", methods=["GET"])', source)
        self.assertIn('@server.route("/about", methods=["GET"])', source)
        self.assertIn('@server.route("/welcome-image", methods=["GET"])', source)
        self.assertIn('@server.route("/post", methods=["POST"])', source)
        self.assertIn("config.ADMIN_PATH + \"/download\"", source)
        self.assertIn("config.ADMIN_PATH + \"/delete\"", source)
        self.assertIn('confirmation == "DELETE"', source)
        self.assertIn("if archive.delete():", source)
        self.assertIn("status=delete-failed", source)

    def test_main_restores_recent_messages_and_uses_honest_label(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("board.restore_recent(config.RESTORE_MESSAGE_COUNT)", source)
        self.assertIn("restored_label=config.RESTORED_TIME_LABEL", source)

    def test_template_values_are_strings_for_phew_escaping(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("message_count_label=(", source)
        self.assertIn("boot_id=str(BOOT_ID)", source)
        self.assertIn('archive_records=str(stats["records"])', source)
        self.assertIn('archive_bytes=str(stats["bytes"])', source)

    def test_pico_html_responses_disable_browser_caching(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('"Cache-Control": "no-store"', source)
        self.assertIn("return html_response(render_template(", source)

    def test_phew_request_logging_is_disabled_and_old_log_removed(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('setattr(logging, name, no_log)', source)
        self.assertIn('os.remove("log.txt")', source)

    def test_vendored_phew_applies_request_policy_before_body_parsing(self):
        source = (ROOT / "phew" / "server.py").read_text(encoding="utf-8")
        policy = (ROOT / "request_policy.py").read_text(encoding="utf-8")
        self.assertIn("response = request_body_error(request.headers)", source)
        self.assertIn("MAX_BODY_BYTES = 4096", policy)
        self.assertIn("multipart/form-data", policy)
        self.assertIn('413: "Payload Too Large"', source)

    def test_readme_uses_bundled_phew_not_incompatible_pypi_release(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("bundled `phew/`", readme)
        self.assertNotIn("micropython-phew", readme)

    def test_readme_explains_http_redirect_and_https_boundary(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("`captive_portal.py`", readme)
        self.assertIn("`http://neverssl.com/`", readme)
        self.assertIn("disconnect and rejoin", readme)
        self.assertIn("HTTPS and HSTS requests cannot be transparently redirected", readme)

    def test_readme_documents_board_first_recovery_and_probe_behavior(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("`/` is the canonical message board", readme)
        self.assertIn("`/welcome`", readme)
        self.assertIn("Apple, Android/ChromeOS, Windows, and Firefox", readme)
        self.assertIn("AAAA and HTTPS DNS queries receive clean no-data answers", readme)
        self.assertIn("`http://192.168.4.1/` as the guaranteed recovery address", readme)

    def test_default_ssid_exposes_recovery_ip_without_changing_board_identity(self):
        source = (ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn('SSID = "BACKPACK-001 OPEN 192.168.4.1"', source)
        self.assertIn('BOARD_NAME = "BACKPACK IN THE PARK"', source)


if __name__ == "__main__":
    unittest.main()
