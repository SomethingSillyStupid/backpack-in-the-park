import unittest

from request_policy import MAX_BODY_BYTES, request_body_error, urlencoded_body_error


class RequestBodyPolicyTests(unittest.TestCase):
    def test_normal_urlencoded_form_is_allowed(self):
        self.assertIsNone(
            request_body_error(
                {
                    "content-length": "400",
                    "content-type": "application/x-www-form-urlencoded",
                }
            )
        )

    def test_oversized_declared_body_is_rejected(self):
        error = request_body_error(
            {
                "content-length": str(MAX_BODY_BYTES + 1),
                "content-type": "application/x-www-form-urlencoded",
            }
        )
        self.assertEqual(error[1], 413)

    def test_multipart_is_rejected_even_with_forged_small_length(self):
        error = request_body_error(
            {
                "content-length": "1",
                "content-type": "multipart/form-data; boundary=woods",
            }
        )
        self.assertEqual(error, ("Multipart forms are not accepted", 415, "text/plain"))

    def test_invalid_content_length_is_rejected(self):
        self.assertEqual(request_body_error({"content-length": "nope"})[1], 400)
        self.assertEqual(request_body_error({"content-length": "-1"})[1], 400)

    def test_truncated_urlencoded_body_is_rejected(self):
        self.assertEqual(urlencoded_body_error(b"message=hel", 13)[1], 400)

    def test_malformed_urlencoded_body_is_rejected(self):
        for body in (b"message", b"message=%", b"message=%2", b"message=%ZZ", b"\xff"):
            with self.subTest(body=body):
                self.assertEqual(urlencoded_body_error(body, len(body))[1], 400)

    def test_complete_urlencoded_unicode_body_is_allowed(self):
        body = b"username=MOTH&message=hello%20%F0%9F%8C%B2"
        self.assertIsNone(urlencoded_body_error(body, len(body)))


if __name__ == "__main__":
    unittest.main()
