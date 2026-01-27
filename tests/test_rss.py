import unittest

from nomadcastd.parsing import encode_show_path
from nomadcastd.rss import rewrite_rss


class RssRewriteTests(unittest.TestCase):
    """Ensure enclosure URLs are rewritten per README rules."""
    def test_rewrite_enclosure(self) -> None:
        rss = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example</title>
    <item>
      <title>Episode 1</title>
      <enclosure url="nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/media/ep1.mp3" length="123" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""
        show_path = encode_show_path("a7c3e9b14f2d6a80715c9e3b1a4d8f20", "BestShow")
        output = rewrite_rss(
            rss_bytes=rss,
            listen_host="127.0.0.1",
            listen_port=5050,
            show_path=show_path,
            cached_filenames={"ep1.mp3"},
            episodes_per_show=5,
            strict_cached=True,
        )
        self.assertIn(
            b"http://127.0.0.1:5050/media/a7c3e9b14f2d6a80715c9e3b1a4d8f20%3ABestShow/ep1.mp3",
            output,
        )

    def test_rewrite_enclosure_with_encoded_filename(self) -> None:
        rss = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example</title>
    <item>
      <title>Episode 1</title>
      <enclosure url="nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/media/Episode%201.mp3" length="123" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""
        show_path = encode_show_path("a7c3e9b14f2d6a80715c9e3b1a4d8f20", "BestShow")
        output = rewrite_rss(
            rss_bytes=rss,
            listen_host="127.0.0.1",
            listen_port=5050,
            show_path=show_path,
            cached_filenames={"Episode 1.mp3"},
            episodes_per_show=5,
            strict_cached=True,
        )
        self.assertIn(
            b"http://127.0.0.1:5050/media/a7c3e9b14f2d6a80715c9e3b1a4d8f20%3ABestShow/Episode%201.mp3",
            output,
        )


if __name__ == "__main__":
    unittest.main()
