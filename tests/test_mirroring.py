import tempfile
import unittest
from pathlib import Path

from nomadcastd.config import (
    add_no_mirror_uri,
    ensure_default_config,
    load_config,
    set_mirroring_enabled,
)
from nomadcastd.mirroring import (
    ensure_symlink,
    mirror_rss_href,
    render_nomadnet_index,
    resolve_mirroring_enabled,
    should_mirror_subscription,
)
from nomadcastd.parsing import encode_show_path, parse_subscription_uri
from nomadcastd.storage import ensure_show_dirs, show_directory


class MirroringTests(unittest.TestCase):
    def test_prompt_persists_mirroring_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            ensure_default_config(config_path)
            config = load_config(config_path)
            answers = iter(["n"])

            def fake_input(_: str) -> str:
                return next(answers)

            enabled = resolve_mirroring_enabled(
                config,
                input_fn=fake_input,
                is_interactive=True,
            )
            self.assertFalse(enabled)
            reloaded = load_config(config_path)
            self.assertFalse(reloaded.mirror_enabled)

    def test_no_mirror_override_supersedes_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            ensure_default_config(config_path)
            set_mirroring_enabled(config_path, True)
            uri = "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow"
            add_no_mirror_uri(config_path, uri)
            config = load_config(config_path)

            self.assertFalse(should_mirror_subscription(config, uri, default_enabled=True))

    def test_symlink_creation_and_repair_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            target = base / "target.txt"
            target.write_text("hello", encoding="utf-8")
            link = base / "link.txt"

            self.assertTrue(ensure_symlink(target, link))
            self.assertFalse(ensure_symlink(target, link))

            other = base / "other.txt"
            other.write_text("other", encoding="utf-8")
            link.unlink()
            link.symlink_to(other)

            self.assertTrue(ensure_symlink(target, link))
            self.assertEqual(link.resolve(), target.resolve())

    def test_nomadnet_index_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            config_path = base / "config"
            storage_path = base / "storage"
            nomadnet_root = base / "nomadnet"
            uri1 = "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow"
            uri2 = "nomadcast:b7c3e9b14f2d6a80715c9e3b1a4d8f20:OtherShow"
            config_path.write_text(
                "\n".join(
                    [
                        "[nomadcast]",
                        f"storage_path = {storage_path}",
                        "",
                        "[subscriptions]",
                        f"uri = {uri1}",
                        f"uri = {uri2}",
                        "",
                        "[mirroring]",
                        f"nomadnet_root = {nomadnet_root}",
                        f"no_mirror_uri = {uri2}",
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config = load_config(config_path)
            subscription1 = parse_subscription_uri(uri1)
            subscription2 = parse_subscription_uri(uri2)
            show_dir = show_directory(config.storage_path, subscription1.destination_hash)
            show_dirs = ensure_show_dirs(show_dir)
            (show_dirs["episodes_dir"] / "episode.mp3").write_bytes(b"test")
            (show_dir / "publisher_rss.xml").write_text(
                "\n".join(
                    [
                        "<rss xmlns:atom=\"http://www.w3.org/2005/Atom\">",
                        "  <channel>",
                        "    <title>Best Show</title>",
                        "    <link>https://example.com</link>",
                        "    <atom:link rel=\"self\" href=\"https://example.com/feed.rss\" />",
                        "    <item>",
                        "      <title>Episode One</title>",
                        "      <enclosure url=\"nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/media/episode.mp3\" />",
                        "    </item>",
                        "  </channel>",
                        "</rss>",
                    ]
                ),
                encoding="utf-8",
            )

            content = render_nomadnet_index(
                config,
                [subscription1, subscription2],
                default_mirroring_enabled=True,
            )
            show_path = encode_show_path(subscription1.destination_hash, subscription1.show_name)
            expected_mirror = mirror_rss_href(subscription1)
            expected_media = f"/file/nomadcast/{show_path}/media/episode.mp3"
            self.assertIn("NOMADCAST INDEX", content)
            self.assertIn("Best Show", content)
            self.assertIn(f"mirror rss`{expected_mirror}", content)
            self.assertIn("example.com`https://example.com", content)
            self.assertIn("origin rss`https://example.com/feed.rss", content)
            self.assertIn("Episode One", content)
            self.assertIn(f"play`{expected_media}", content)
            self.assertIn("OtherShow", content)
            self.assertIn("mirror rss`#", content)
            self.assertIn(show_path, expected_mirror)


if __name__ == "__main__":
    unittest.main()
