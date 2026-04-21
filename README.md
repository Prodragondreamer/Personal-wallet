# Personal Wallet (Kivy MVP)

A personal crypto wallet mobile app built with Python and Kivy, featuring real-time prices, encrypted local storage, and a blockchain Kill Switch.

**Team:** Joseph Majcherek · DJ Martinez · Adriel Moronta · Doyle Bradford · Chandler Isma

---

## Getting Started

### Requirements
- Python 3.11
- Git

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/Prodragondreamer/Personal-wallet.git
cd Personal-wallet

# 2. Switch to the main branch
git checkout backend-and-security

# 3. Create and activate a virtual environment
py -3.11 -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the app
python main.py
```

---

## First-Time Setup (Inside the App)

1. Open the **Vault** tab in the bottom navigation
2. Enter a passphrase (8+ characters) and tap **Create vault**
3. After restarting, tap **Unlock** to restore your session

---

## Features

- **Unified Dashboard** — live portfolio total combining crypto and stocks via Heroku price relay
- **Encrypted Vault** — balances and keys stored as Fernet ciphertext
- **Kill Switch** — instantly freezes all transactions when activated; toggle in Vault settings
- **Transaction Foresight** — preview gas fees and resulting balance before confirming a send
- **Price Relay** — Heroku server fetches prices from CoinGecko and Yahoo Finance with 60-second caching and fallback to last known values

---

## Project Structure

```
Personal-wallet/
├── main.py                      # App entry point
├── requirements.txt
├── cloudfolder/                 # Heroku price relay API
│   ├── api.py
│   ├── Procfile
│   ├── requirements.txt
│   └── runtime.txt
├── walletapp/
│   ├── app.py                   # Kivy app and screen manager
│   ├── models.py                # Asset, TransactionDraft, TransactionPreview
│   ├── screens/                 # Dashboard, Asset Entry, Preview, Vault
│   ├── services/                # Backend, SecureWalletBackend, MarketService
│   ├── persistence/             # SQLite, encryption, repositories
│   └── ui/wallet.kv             # Kivy layout file
└── tests/
    ├── test_suite.py            # QA tests (FR-01 through FR-04 + security)
    ├── test_backend.py          # StubBackend unit tests
    └── transaction_log.py       # Transaction and bug log
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Backend

The app uses `SecureWalletBackend` (`walletapp/services/secure_backend.py`) with:

- **SQLite** (`wallet.db` under the Kivy app `user_data_dir`) for holdings and settings
- **Encryption at rest** — balances and settings are Fernet ciphertext
- **Private key material** — stored only as ciphertext; cleartext exists in memory only during signing, never logged
- **Lock / unlock** — Lock clears derived keys from memory; all reads return empty and sends are rejected until unlocked
