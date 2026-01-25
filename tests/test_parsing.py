import unittest

from nomadcastd.parsing import decode_show_path, encode_show_path, parse_subscription_uri


class ParsingTests(unittest.TestCase):
    """Validate README subscription and show_path parsing rules."""
    def test_parse_subscription_uri(self) -> None:
        uri = "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/rss"
        subscription = parse_subscription_uri(uri)
        self.assertEqual(subscription.destination_hash, "a7c3e9b14f2d6a80715c9e3b1a4d8f20")
        self.assertEqual(subscription.show_name, "BestShow")

    def test_parse_subscription_uri_with_double_slash(self) -> None:
        uri = "nomadcast://a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/rss"
        subscription = parse_subscription_uri(uri)
        self.assertEqual(subscription.destination_hash, "a7c3e9b14f2d6a80715c9e3b1a4d8f20")
        self.assertEqual(subscription.show_name, "BestShow")

    def test_show_path_roundtrip(self) -> None:
        destination = "a7c3e9b14f2d6a80715c9e3b1a4d8f20"
        show_name = "BestShow"
        show_path = encode_show_path(destination, show_name)
        parsed_destination, parsed_show = decode_show_path(show_path)
        self.assertEqual(parsed_destination, destination)
        self.assertEqual(parsed_show, show_name)


if __name__ == "__main__":
    unittest.main()
