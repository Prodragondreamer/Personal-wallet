# Personal Wallet (Prototype)

Prototype “personal wallet” that shows a unified view of balances, demonstrates a kill-switch gate, and connects to Ethereum Sepolia for RPC health.

This folder contains:
- A **fast desktop UI** using **Tkinter** (standard library): `main.py`
- An **optional Kivy UI** (heavier install): `main_kivy.py`
- A small backend service module: `safeguard_vault.py`

## What this prototype is (and is not)

- **This is**: a runnable UI + a small service layer showing how you’d *structure* a wallet dashboard, a manual balance store, a network health indicator, and a kill-switch “gate”.
- **This is not**: a production wallet. It **does not** manage private keys, sign transactions, or move funds on-chain.

## Deployment note (Heroku / cloud)

The **class/project target** is to deploy a small backend component to a cloud platform such as **Heroku** (e.g., a Flask API that serves balances / health / prices).

- **Current repo state**: this repository is primarily a **local runnable prototype** (desktop UI + service module). A full Heroku-ready web backend (e.g., `Procfile`, Flask app entrypoint, config, routes) is **not fully wired in yet**.
- **How we describe it in a presentation**: “Designed to be Heroku-deployable; cloud configuration uses environment variables; prototype currently runs locally.”

## High-level architecture

```text
          UI (Tkinter or Kivy)
   main.py / main_kivy.py
            |
            | calls
            v
   safeguard_vault.SafeguardVault
     |            |
     |            +--> Market data (yfinance) [optional demo]
     |
     +--> Web3 RPC (Sepolia) [health + endpoint chosen]
     |
     +--> SQLite (manual bank balance) [prototype store]
```

## Quick start (recommended: Tkinter UI)

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### What you’ll see
- **Overview**: Total net worth (Bank + Stocks + Crypto), plus Sepolia RPC status and the endpoint used.
- **Add assets**: Enter values for Bank/Stocks/Crypto and Save.
- **Transaction preview**: Placeholder preview + Confirm (blocked when kill switch is on).
- **Kill switch**: Puts the app into a paused state and blocks confirmation.

### UI flow (more detail)

- **Overview**
  - Displays: Total, Bank, Stocks, Crypto
  - Displays: RPC status and selected endpoint (useful for debugging Sepolia connectivity)
  - Actions:
    - **Add assets** -> opens the asset entry form
    - **Preview transaction** -> opens the preview screen
    - **Kill switch** -> flips the app into a paused state (blocks confirmation)

- **Add assets**
  - Inputs: Bank / Stocks / Crypto (numbers)
  - Save behavior:
    - Updates UI state immediately
    - Also syncs Bank into the backend `SafeguardVault` storage when available

- **Transaction preview**
  - Prototype-only placeholders for price/gas/total
  - Confirm is blocked when kill switch is enabled

## Optional: Kivy UI

Kivy is a large dependency and can take a while to install.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-kivy.txt
python main_kivy.py
```

## Backend / service layer

The backend logic is in `safeguard_vault.py`.

### RPC configuration (Sepolia)

By default the app tries RPC URLs in priority order:
1. `INFURA_PROJECT_ID` (Infura Sepolia)
2. `ETH_SEPOLIA_RPC_URL` (any custom RPC)
3. A small list of public Sepolia endpoints

Set env vars like:

```bash
export INFURA_PROJECT_ID="..."
# or
export ETH_SEPOLIA_RPC_URL="https://your-sepolia-rpc"
```

Optional: create a local `.env` file (gitignored). See `.env.example`.

### How RPC health is determined

The vault considers the RPC “up” if either:
- `w3.is_connected()` succeeds, or
- `w3.eth.block_number` returns without error

This helps with RPC endpoints that behave differently under Web3’s default connectivity probe.

### Local storage (prototype)

`SafeguardVault` stores the **manual bank balance** in a small SQLite table.
Current mode uses an **in-memory** database, so values reset when the app restarts.

Schema (conceptual):

```sql
CREATE TABLE IF NOT EXISTS balance (amount REAL);
```

Current behavior:
- On update, the table is cleared and the latest value is inserted (treating it as the “current” balance).

### Market data (demo)

`SafeguardVault.get_unified_balance()` can fetch a market price via `yfinance` and add it to the manual bank balance.
This is a **demo** for the “unified net worth” concept; it is not a full portfolio engine.

## CLI smoke test

```bash
source .venv/bin/activate
python main-2.py
```

Enable the yfinance demo path:

```bash
RUN_UNIFIED_DEMO=1 python main-2.py
```

## Tests

```bash
source .venv/bin/activate
python test_vault-2.py
```

## Troubleshooting

### “RPC not connected”

- Public endpoints can be flaky/rate-limited. Prefer setting one of:
  - `INFURA_PROJECT_ID`
  - `ETH_SEPOLIA_RPC_URL`
- Confirm your machine has outbound HTTPS access to the RPC host.

### “Nothing shows up” when launching the UI

- The Tkinter UI should appear immediately. If it doesn’t:
  - Try launching from a normal terminal: `python main.py`
  - Use ⌘+Tab / Mission Control to bring the window to the front
  - If you’re in a remote/SSH environment, the GUI may not display locally

### Kivy install is slow

- Kivy is large and may require system dependencies depending on your Python/macOS version.
- Use `main.py` (Tkinter) for the fastest demo experience.

## Dependency notes

- `requirements.txt` is kept intentionally small for fast installs (Tkinter uses the standard library).
- `requirements-full.txt` mirrors the broader dependency set seen upstream (Kivy/Flask/etc).

## Project structure

```text
main.py                 # Tkinter UI (recommended)
main_kivy.py            # Optional Kivy UI
safeguard_vault.py      # Backend service module
main-2.py               # CLI smoke test
test_vault-2.py         # Unit tests (prototype)
requirements.txt        # Minimal deps (fast)
requirements-kivy.txt   # Adds Kivy on top
requirements-full.txt   # Full/experimental deps list
screens/                # Kivy screens (prototype)
```

## Roadmap / next steps (if you extend the prototype)

- **Transaction foresight**: real gas estimation + balance impact simulation
- **Kill switch on-chain**: wire the UI to a smart contract and add authorization
- **Persistent storage**: encrypted DB + key management (if storing data across sessions)
- **API reliability**: caching, retries with backoff, and request budgeting (rate limit handling)


#Small preview
<img width="381" height="642" alt="Screen Shot 2026-04-21 at 8 19 44 AM" src="https://github.com/user-attachments/assets/76524d28-e9ba-4a5d-a085-acad882d986e" />

