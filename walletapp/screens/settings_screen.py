from __future__ import annotations
from kivy.app import App
from kivy.properties import BooleanProperty, StringProperty

from walletapp.exceptions import VaultError
from walletapp.screens.base import WalletScreen
from walletapp.services.secure_backend import SecureWalletBackend


class SettingsSecurityScreen(WalletScreen):
    killswitch_enabled = BooleanProperty(False)
    status_text = StringProperty("")
    vault_hint = StringProperty("")

    def on_pre_enter(self, *args) -> None:
        self.status_text = ""
        app = self.manager.app  # type: ignore[attr-defined]
        b = app.backend
        if isinstance(b, SecureWalletBackend):
            if b.vault_exists() and b.is_unlocked:
                prefs = b.load_security_settings()
                self.killswitch_enabled = prefs["killswitch_enabled"]
                self.vault_hint = "Vault unlocked. You can lock it or change security options."
            elif b.vault_exists():
                self.vault_hint = "Vault is locked. Enter your passphrase and tap Unlock."
            else:
                self.vault_hint = "No vault yet. Choose a passphrase (8+ characters) and tap Create vault."
        else:
            self.vault_hint = ""

    def toggle_killswitch(self, enabled: bool) -> None:
        self.killswitch_enabled = enabled
        app = self.manager.app  # type: ignore[attr-defined]
        b = app.backend
        if isinstance(b, SecureWalletBackend) and b.is_unlocked:
            self.status_text = (
                "Kill switch will be saved when you tap Save."
                if enabled
                else "Kill switch disabled (save to apply)."
            )
        else:
            self.status_text = (
                "Kill switch enabled (transactions blocked)."
                if enabled
                else "Kill switch disabled."
            )

    def _passphrase(self) -> str:
        ti = self.ids.get("passphrase_input")
        if ti is None:
            return ""
        return (ti.text or "").strip()

    def _clear_passphrase_field(self) -> None:
        ti = self.ids.get("passphrase_input")
        if ti is not None:
            ti.text = ""

    def create_vault(self) -> None:
        app = self.manager.app  # type: ignore[attr-defined]
        b = app.backend
        if not isinstance(b, SecureWalletBackend):
            self.status_text = "This build uses a non-secure backend."
            return
        pw = self._passphrase()
        try:
            b.initialize_vault(pw)
        except VaultError as e:
            self.status_text = str(e)
            return
        self._clear_passphrase_field()
        self.status_text = "Vault created and unlocked. Default test assets loaded."
        self.vault_hint = "Vault unlocked."
        self._refresh_main()

    def unlock_vault(self) -> None:
        app = self.manager.app  # type: ignore[attr-defined]
        b = app.backend
        if not isinstance(b, SecureWalletBackend):
            return
        pw = self._passphrase()
        if not b.unlock(pw):
            self.status_text = "Unlock failed. Wrong passphrase or corrupted database."
            return
        self._clear_passphrase_field()
        self.status_text = "Unlocked."
        prefs = b.load_security_settings()
        self.killswitch_enabled = prefs["killswitch_enabled"]
        self.vault_hint = "Vault unlocked."
        self._refresh_main()

    def lock_vault(self) -> None:
        app = self.manager.app  # type: ignore[attr-defined]
        b = app.backend
        if isinstance(b, SecureWalletBackend):
            b.lock()
        self._clear_passphrase_field()
        self.status_text = "Vault locked. Passphrase cleared from memory."
        self.vault_hint = "Vault is locked."
        self._refresh_main()

def reset_vault(self):
        app = App.get_running_app()
    
        try:
           
            app.backend.reset_vault(confirm=True)
            self.status_text = "Vault reset successfully."

            # Update UI state
            self.vault_hint = "No vault yet. Create a new one."
            self._refresh_main()
    
        except VaultError as e:
         self.status_text = str(e)
        except AttributeError:
              self.status_text = "Backend is not initialized."
        def save_settings(self) -> None:
            app = self.manager.app  # type: ignore[attr-defined]
            b = app.backend
            if isinstance(b, SecureWalletBackend):
                if not b.is_unlocked:
                    self.status_text = "Unlock the vault before saving settings."
                    return
                try:
                    b.save_security_settings(
                        self.killswitch_enabled,
                        require_pin=False,
                        biometrics=False,
                    )
                except VaultError as e:
                    self.status_text = str(e)
                    return
            self.status_text = "Settings saved."

     def _refresh_main(self) -> None:
        try:
            main = self.manager.get_screen("main")  # type: ignore[attr-defined]
            main.on_pre_enter()
        except Exception:
            pass
