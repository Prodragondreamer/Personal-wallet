from __future__ import annotations

import os
from typing import Any

from kivy.app import App
from kivy.core.text import LabelBase
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, SlideTransition

from walletapp.services.backend import BackendController
from walletapp.services.secure_backend import SecureWalletBackend
from walletapp.screens.asset_entry_screen import AssetEntryScreen
from walletapp.screens.add_funds_screen import AddFundsScreen
from walletapp.screens.main_screen import MainScreen
from walletapp.screens.markets_screen import MarketsScreen
from walletapp.screens.settings_screen import SettingsSecurityScreen
from walletapp.screens.tx_preview_screen import TransactionPreviewScreen
from walletapp.widgets.line_chart import LineChart  # noqa: F401
from walletapp.widgets.market_row import MarketRow  # noqa: F401
from walletapp.widgets.pie_chart import PieChart  # noqa: F401


class WalletScreenManager(ScreenManager):
    """
    ScreenManager subclass so screens can access `manager.app`.
    """

    app: "PersonalWalletApp"

    # tab ordering for left/right slide direction
    tab_order = ["main", "markets", "add_funds", "asset_entry", "tx_preview", "settings"]

    def set_current(self, name: str) -> None:
        """
        Switch screens with a natural slide direction:
        - If the target tab is to the left, slide left.
        - If the target tab is to the right, slide right.
        """
        if name == self.current or name not in self.tab_order:
            self.current = name
            return

        try:
            cur_i = self.tab_order.index(self.current)
        except ValueError:
            cur_i = 0
        tgt_i = self.tab_order.index(name)

        direction = "right" if tgt_i < cur_i else "left"
        self.transition = SlideTransition(direction=direction, duration=0.30)
        self.current = name


class PersonalWalletApp(App):
    title = "Personal Wallet (MVP)"

    def __init__(self, backend: BackendController | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if backend is not None:
            self.backend: BackendController = backend
        else:
            db_path = os.path.join(self.user_data_dir, "wallet.db")
            self.backend = SecureWalletBackend(db_path)
        self.state: dict[str, Any] = {}
        self.btn_gloss_tex = self._make_gloss_texture(max_alpha=0.22)
        self.btn_gloss_tex_subtle = self._make_gloss_texture(max_alpha=0.14)
        self.btn_gloss_tex_icon = self._make_gloss_texture(max_alpha=0.16)

    def _make_gloss_texture(self, *, max_alpha: float) -> Texture:
        """
        1x256 vertical alpha gradient texture for smooth button highlight.
        Using a texture avoids visible banding from stacked rectangles.
        """
        w, h = 1, 256
        tex = Texture.create(size=(w, h), colorfmt="rgba")
        tex.wrap = "clamp_to_edge"
        tex.mag_filter = "linear"
        tex.min_filter = "linear"

        # Top-heavy gloss: strong at the very top, fades smoothly to 0.
        buf = bytearray()
        for y in range(h):
            t = y / float(h - 1)  # 0 bottom -> 1 top (we'll invert)
            x = 1.0 - t
            # Ease-out curve + extra top bias
            a = max_alpha * (x * x) * (0.85 + 0.15 * x)
            alpha = int(max(0.0, min(1.0, a)) * 255)
            buf.extend([255, 255, 255, alpha])
        tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
        tex.flip_vertical()
        return tex

    def on_start(self) -> None:
        b = self.backend
        if not isinstance(b, SecureWalletBackend):
            return
        init_pw   = os.environ.get("PERSONAL_WALLET_INIT_PASSPHRASE", "")
        unlock_pw = os.environ.get("PERSONAL_WALLET_PASSPHRASE", "")
        if not b.vault_exists():
            if len(init_pw) >= 8:
                b.initialize_vault(init_pw)
        elif unlock_pw:
            b.unlock(unlock_pw)

    def build(self) -> WalletScreenManager:
        LabelBase.register(
            name="MaterialIcons",
            fn_regular="walletapp/ui/assets/fonts/MaterialIcons-Regular.ttf",
        )
        Builder.load_file("walletapp/ui/wallet.kv")

        # dismiss keyboard when tapping outside a text field 
        Window.bind(on_touch_down=self._dismiss_keyboard)

        sm = WalletScreenManager()
        sm.app = self
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(MarketsScreen(name="markets"))
        sm.add_widget(AddFundsScreen(name="add_funds"))
        sm.add_widget(AssetEntryScreen(name="asset_entry"))
        sm.add_widget(TransactionPreviewScreen(name="tx_preview"))
        sm.add_widget(SettingsSecurityScreen(name="settings"))
        sm.current = "main"
        return sm

    def _dismiss_keyboard(self, window, touch):
        from kivy.base import EventLoop
        from kivy.uix.textinput import TextInput
        win = EventLoop.window
        if win:
            focused = [w for w in win.children if isinstance(w, TextInput) and w.focus]
            if not focused:
                win.release_all_keyboards()

