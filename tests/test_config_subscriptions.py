import tempfile
import unittest
from pathlib import Path

from nomadcastd.config import add_subscription_uri, load_subscriptions, remove_subscription_uri


class ConfigSubscriptionTests(unittest.TestCase):
    def test_add_and_remove_subscription_uri(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            uri = "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow"
            second_uri = "nomadcast:b7c3e9b14f2d6a80715c9e3b1a4d8f20:OtherShow"

            self.assertTrue(add_subscription_uri(config_path, uri))
            self.assertTrue(add_subscription_uri(config_path, second_uri))
            self.assertFalse(add_subscription_uri(config_path, uri))
            self.assertEqual(load_subscriptions(config_path), [uri, second_uri])

            self.assertTrue(remove_subscription_uri(config_path, uri))
            self.assertFalse(remove_subscription_uri(config_path, uri))
            self.assertEqual(load_subscriptions(config_path), [second_uri])


if __name__ == "__main__":
    unittest.main()
