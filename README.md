# AxiomRx - Desktop Application Architecture

> **Notice:** This is an open-source project developed by **Hassan Gasim** for everyone who needs it. Enjoy!


A robust offline Windows desktop application using Python, PyQt6, and SQLite.

## Features
- **Offline Architecture**: Fully localized using SQLite and completely offline by design. 
- **PyQt6 UI**: Built for the Windows desktop ecosystem using Python's bindings for the Qt framework.
- **Robust Database State Management**: Implements `WAL` (Write-Ahead Logging) and `busy_timeout` configuration to gracefully handle SQLite database locking for concurrency.
- **Normalized Schema**: Structured securely as per architectural requirements (`Products`, `Sales`, `SalesDetails`).

## Project Layout

- `database.py`: Core connectivity, schema generation, transaction boundaries, and SQLite lock handling.
- `crud.py`: Base operations representing Products insertion/fetching and Point of Sale atomic transactions.
- `main.py`: Bootstraps the PyQt6 UI offline and checks database health on initialization.

## Setup Instructions

1. **Install dependencies**:
   Run the following from your terminal to install the PyQt6 UI framework:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Run the Initialization App**:
   Running `main.py` builds your `axiom_rx.db` schema immediately if it doesn't exist, applying all robust PRAGMA configurations, and launches the UI.
   ```powershell
   python main.py
   ```
