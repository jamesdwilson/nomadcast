import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nomadcast import app_install


class AppInstallTests(unittest.TestCase):
    def test_install_target_windows_uses_local_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_app_data = Path(temp_dir) / "LocalAppData"
            local_app_data.mkdir(parents=True, exist_ok=True)

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}):
                with mock.patch("nomadcast.app_install.platform.system", return_value="Windows"):
                    with mock.patch("nomadcast.app_install.os.access", return_value=True):
                        target = app_install._install_target()

        self.assertIsNotNone(target)
        assert target is not None
        expected_dir = local_app_data / "Programs" / app_install.APP_NAME
        self.assertEqual(target.install_dir, expected_dir)
        self.assertEqual(target.launcher_path, expected_dir / "NomadCast.cmd")

    def test_install_windows_app_writes_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "Programs" / app_install.APP_NAME
            target = app_install.InstallTarget(
                platform="Windows",
                install_dir=target_dir,
                display_target=str(target_dir),
                launcher_path=target_dir / "NomadCast.cmd",
            )

            launcher_path = app_install._install_windows_app(target)

            self.assertTrue(launcher_path.exists())
            launcher_text = launcher_path.read_text(encoding="utf-8")
            self.assertIn(sys.executable, launcher_text)

    def test_install_linux_app_creates_launcher_and_desktop_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            data_dir = Path(temp_dir) / "xdg-data"
            bin_dir = Path(temp_dir) / "xdg-bin"
            home_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            bin_dir.mkdir(parents=True, exist_ok=True)

            with mock.patch.dict(
                os.environ,
                {"XDG_DATA_HOME": str(data_dir), "XDG_BIN_HOME": str(bin_dir)},
            ):
                with mock.patch("nomadcast.app_install.platform.system", return_value="Linux"):
                    with mock.patch("nomadcast.app_install.Path.home", return_value=home_dir):
                        target = app_install._install_target()

                        assert target is not None
                        launcher_path = app_install._install_linux_app(target)

            self.assertTrue(launcher_path.exists())
            desktop_entry_path = data_dir / "applications" / "nomadcast.desktop"
            self.assertTrue(desktop_entry_path.exists())

            desktop_text = desktop_entry_path.read_text(encoding="utf-8")
            self.assertIn(f"Exec={launcher_path}", desktop_text)
            self.assertIn("Name=NomadCast", desktop_text)
            self.assertIn("Type=Application", desktop_text)


if __name__ == "__main__":
    unittest.main()
