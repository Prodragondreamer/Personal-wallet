# Personal Wallet (Kivy MVP)

Kivy MVP for a personal crypto wallet with **local encrypted persistence** (assignment: Local Persistence — SQLite + encrypted sensitive fields, `EncryptionService`, repositories).

## Run

```bash
cd personal_wallet_kivy_mvp
pip install -r requirements.txt
python3 main.py
```

## Backend (secure MVP)

The app uses `SecureWalletBackend` (`walletapp/services/secure_backend.py`) with:

- **SQLite** (`wallet.db` under the Kivy app `user_data_dir`) for holdings and settings.
- **Encryption at rest**: balances and settings values are **Fernet** ciphertext; a random **salt** and **PBKDF2-HMAC-SHA256** (high iteration count) derive keys from your **passphrase** (passphrase is not stored).
- **Private key material**: optional demo signing key bytes live only as ciphertext in `wallet_keys`; cleartext exists in memory only when decrypted for future signing (never logged).
- **Lock / unlock**: **Lock** clears derived keys from memory. Without a successful unlock, portfolio reads return empty / zero and sends are rejected.

### First-time setup (UI)

1. Open **Settings**.
2. Enter a passphrase (8+ characters) and tap **Create vault** (once per device DB).
3. Tap **Unlock** after restarts.

### Optional environment variables (automation / dev)

- `PERSONAL_WALLET_INIT_PASSPHRASE` — if set (8+ chars) and no vault exists yet, creates the vault on startup.
- `PERSONAL_WALLET_PASSPHRASE` — if set and a vault exists, unlocks on startup.

Do not use these in production builds; prefer OS secure storage and user-only unlock for real deployments.

## Interface for UI

`walletapp/services/backend.py` defines `BackendController` and `StubBackend` (still available for tests). The app wires `SecureWalletBackend` by default in `walletapp/app.py`.
