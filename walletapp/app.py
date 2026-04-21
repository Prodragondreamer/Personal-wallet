from __future__ import annotations
 
import os
from typing import Any
 
from kivy.app import App
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, SlideTransition
 
from walletapp.services.backend import BackendController
from walletapp.services.secure_backend import SecureWalletBackend
from walletapp.screens.asset_entry_screen import AssetEntryScreen
from walletapp.screens.main_screen import MainScreen
from walletapp.screens.settings_screen import SettingsSecurityScreen
from walletapp.screens.tx_preview_screen import TransactionPreviewScreen
from walletapp.widgets.pie_chart import PieChart  # noqa: F401
 
 
class WalletScreenManager(ScreenManager):
    """
    ScreenManager subclass so screens can access `manager.app`.
    """
 
    app: "PersonalWalletApp"
 
    # Defines tab ordering for left/right slide direction.
    tab_order = ["main", "asset_entry", "tx_preview", "settings"]
 
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
 
        # User preference:
        # - Tap a tab to the right -> slide new screen in from the right (content shifts left)
        # - Tap a tab to the left  -> slide new screen in from the left  (content shifts right)
        direction = "right" if tgt_i < cur_i else "left"
        # Slightly slower on purpose for a smoother feel.
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
 
    def on_start(self) -> None:
        b = self.backend
        if not isinstance(b, SecureWalletBackend):
            return
        init_pw = os.environ.get("PERSONAL_WALLET_INIT_PASSPHRASE", "")
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
 
        sm = WalletScreenManager()
        sm.app = self
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(AssetEntryScreen(name="asset_entry"))
        sm.add_widget(TransactionPreviewScreen(name="tx_preview"))
        sm.add_widget(SettingsSecurityScreen(name="settings"))
        sm.current = "main"
        return sm



