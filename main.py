"""
Entry point.

Configured to *feel like a mobile app* during desktop development, without forcing
any window behavior on real Android/iOS builds.
"""

from kivy.config import Config
from kivy.utils import platform


def _configure_for_mobile_first_dev() -> None:
    # These Config values must be set before importing most other Kivy modules.
    if platform not in ("android", "ios"):
        # Phone-ish preview size (desktop only).
        Config.set("graphics", "width", "390")
        Config.set("graphics", "height", "844")
        Config.set("graphics", "resizable", "0")

    # Keep content visible when keyboard opens (mobile-friendly default).
    Config.set("kivy", "keyboard_mode", "systemandmulti")
    Config.set("kivy", "exit_on_escape", "0")


_configure_for_mobile_first_dev()

from walletapp.app import PersonalWalletApp  # noqa: E402


if __name__ == "__main__":
    PersonalWalletApp().run()

