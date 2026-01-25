from __future__ import annotations

"""NomadCast v0 UI helpers.

This module focuses on the minimal Kivy-based flow described in the README:
collect a show locator, write it to config, and open the local feed URL in the
system's podcast handler.
"""

import importlib.util
import textwrap
import webbrowser
from dataclasses import dataclass
from typing import Callable

from nomadcastd.config import NomadCastConfig, add_subscription_uri, load_config
from nomadcastd.parsing import (
    Subscription,
    encode_show_path,
    normalize_subscription_input,
    parse_subscription_uri,
)


def _subscription_feed_url(subscription: Subscription, config: NomadCastConfig) -> str:
    """Build the local HTTP feed URL for a subscription."""
    host = config.public_host or config.listen_host
    if host == "0.0.0.0":
        host = "127.0.0.1"
    show_path = encode_show_path(subscription.destination_hash, subscription.show_name)
    return f"http://{host}:{config.listen_port}/feeds/{show_path}"


def _podcast_handler_url(feed_url: str) -> str:
    """Convert an HTTP feed URL into a podcast:// handler URL."""
    if feed_url.startswith("http://"):
        return f"podcast://{feed_url[len('http://'):] }"
    if feed_url.startswith("https://"):
        return f"podcast://{feed_url[len('https://'):] }"
    return feed_url


@dataclass(frozen=True)
class UiStatus:
    """Lightweight status payload for UI updates."""

    message: str
    is_error: bool = False


class SubscriptionService:
    """Service wrapper for subscription writes and podcast handler launches."""

    def __init__(self, config_loader: Callable[[], NomadCastConfig] = load_config) -> None:
        self._config_loader = config_loader

    def add_subscription(self, locator: str) -> UiStatus:
        """Add a subscription and open the podcast handler URL."""
        uri = normalize_subscription_input(locator)
        subscription = parse_subscription_uri(uri)
        config = self._config_loader()
        added = add_subscription_uri(config.config_path, uri)

        feed_url = _subscription_feed_url(subscription, config)
        handler_url = _podcast_handler_url(feed_url)
        webbrowser.open(handler_url, new=2)

        if added:
            return UiStatus(
                message=f"Added subscription. Opening podcast app for {feed_url}.",
                is_error=False,
            )

        return UiStatus(
            message=f"Subscription already exists. Opening podcast app for {feed_url}.",
            is_error=False,
        )

    def manage_daemon(self) -> UiStatus:
        """Future roadmap stub: manage the daemon lifecycle."""
        raise NotImplementedError("Daemon management UI is not implemented yet.")

    def edit_subscriptions(self) -> UiStatus:
        """Future roadmap stub: edit subscribed feeds."""
        raise NotImplementedError("Subscription editor is not implemented yet.")

    def view_cache_status(self) -> UiStatus:
        """Future roadmap stub: view cache status."""
        raise NotImplementedError("Cache status view is not implemented yet.")

    def system_tray_integration(self) -> UiStatus:
        """Future roadmap stub: system tray integration."""
        raise NotImplementedError("System tray integration is not implemented yet.")

    def health_endpoint(self) -> UiStatus:
        """Future roadmap stub: local health endpoint UI."""
        raise NotImplementedError("Health endpoint UI is not implemented yet.")


class UiUnavailableError(RuntimeError):
    """Raised when the Kivy UI cannot be launched."""


class UiLauncher:
    """Kivy UI launcher for the NomadCast v0 application."""

    def __init__(self, initial_locator: str | None = None) -> None:
        self._initial_locator = initial_locator

    def ensure_kivy_available(self) -> None:
        """Ensure Kivy can be imported before building the UI."""
        if importlib.util.find_spec("kivy") is None:
            message = textwrap.dedent(
                """
                Kivy is required for the NomadCast UI.
                Install it with: pip install kivy
                """
            ).strip()
            raise UiUnavailableError(message)

    def launch(self) -> None:
        """Launch the NomadCast UI application."""
        self.ensure_kivy_available()
        from kivy.app import App
        from kivy.core.window import Window
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.textinput import TextInput

        service = SubscriptionService()
        initial_locator = self._initial_locator or ""

        class NomadCastApp(App):
            """NomadCast v0 Kivy UI."""

            def build(self) -> BoxLayout:  # type: ignore[override]
                Window.minimum_width = 720
                Window.minimum_height = 420
                Window.clearcolor = (0.07, 0.09, 0.12, 1.0)

                root = BoxLayout(orientation="vertical", padding=24, spacing=16)

                header = Label(
                    text="[b]NomadCast v0[/b]",
                    markup=True,
                    font_size=28,
                    color=(0.9, 0.93, 0.96, 1.0),
                    size_hint_y=None,
                    height=48,
                )
                root.add_widget(header)

                subtitle = Label(
                    text=(
                        "Paste a NomadCast locator to subscribe. "
                        "NomadCast will add the feed to your local daemon and open "
                        "your podcast app."
                    ),
                    font_size=16,
                    color=(0.75, 0.8, 0.86, 1.0),
                    size_hint_y=None,
                    height=60,
                )
                root.add_widget(subtitle)

                self.locator_input = TextInput(
                    text=initial_locator,
                    hint_text="nomadcast:<destination_hash>:<ShowName>/rss",
                    size_hint_y=None,
                    height=44,
                    multiline=False,
                    foreground_color=(0.93, 0.95, 0.97, 1.0),
                    background_color=(0.13, 0.15, 0.19, 1.0),
                    cursor_color=(0.98, 0.76, 0.35, 1.0),
                )
                root.add_widget(self.locator_input)

                button_row = BoxLayout(size_hint_y=None, height=48, spacing=12)
                add_button = Button(
                    text="Add subscription",
                    background_color=(0.2, 0.5, 0.78, 1.0),
                    color=(1, 1, 1, 1),
                )
                add_button.bind(on_press=self._handle_add)
                button_row.add_widget(add_button)

                daemon_button = Button(text="Manage daemon", background_color=(0.2, 0.2, 0.28, 1.0))
                daemon_button.bind(on_press=self._handle_not_implemented(service.manage_daemon))
                button_row.add_widget(daemon_button)

                subscriptions_button = Button(
                    text="Edit subscriptions", background_color=(0.2, 0.2, 0.28, 1.0)
                )
                subscriptions_button.bind(on_press=self._handle_not_implemented(service.edit_subscriptions))
                button_row.add_widget(subscriptions_button)

                cache_button = Button(text="View cache", background_color=(0.2, 0.2, 0.28, 1.0))
                cache_button.bind(on_press=self._handle_not_implemented(service.view_cache_status))
                button_row.add_widget(cache_button)
                root.add_widget(button_row)

                future_row = BoxLayout(size_hint_y=None, height=48, spacing=12)
                tray_button = Button(text="System tray", background_color=(0.2, 0.2, 0.28, 1.0))
                tray_button.bind(on_press=self._handle_not_implemented(service.system_tray_integration))
                future_row.add_widget(tray_button)

                health_button = Button(text="Health endpoint", background_color=(0.2, 0.2, 0.28, 1.0))
                health_button.bind(on_press=self._handle_not_implemented(service.health_endpoint))
                future_row.add_widget(health_button)
                root.add_widget(future_row)

                self.status_label = Label(
                    text="Ready to add a show.",
                    font_size=14,
                    color=(0.72, 0.78, 0.85, 1.0),
                    size_hint_y=None,
                    height=36,
                )
                root.add_widget(self.status_label)

                return root

            def _set_status(self, status: UiStatus) -> None:
                self.status_label.text = status.message
                if status.is_error:
                    self.status_label.color = (0.95, 0.5, 0.45, 1.0)
                else:
                    self.status_label.color = (0.72, 0.9, 0.7, 1.0)

            def _handle_add(self, *_: object) -> None:
                locator = self.locator_input.text
                try:
                    status = service.add_subscription(locator)
                except ValueError as exc:
                    status = UiStatus(message=f"Invalid locator: {exc}", is_error=True)
                except OSError as exc:
                    status = UiStatus(message=f"Failed to update config: {exc}", is_error=True)
                self._set_status(status)

            def _handle_not_implemented(
                self, action: Callable[[], UiStatus]
            ) -> Callable[[object], None]:
                def handler(_: object) -> None:
                    try:
                        status = action()
                    except NotImplementedError as exc:
                        status = UiStatus(message=str(exc), is_error=True)
                    self._set_status(status)

                return handler

        NomadCastApp().run()
