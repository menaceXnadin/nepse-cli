# Nepse CLI - Meroshare IPO Automation & Market Data

[![PyPI version](https://badge.fury.io/py/nepse-cli.svg)](https://badge.fury.io/py/nepse-cli)
[![Python Version](https://img.shields.io/pypi/pyversions/nepse-cli.svg)](https://pypi.org/project/nepse-cli/)

![Nepse CLI](nepse-cli-image.png)

A modern, interactive command-line tool to automate IPO applications on Meroshare for multiple family members and view real-time NEPSE market data.

**✨ Now featuring a beautiful TUI with Rich tables, interactive menus, and fuzzy search!**

```
[██████████████████░░░░░░░░░░░░] 50% (3/6) Selecting DP (value: 10900)...
```

## Installation

### Option 1: Install from PyPI (Recommended)
```bash
pip install nepse-cli
```

### Option 2: Install from Source (For Development)
```powershell
cd "Nepse CLI"
pip install -e .
```

### 🚀 Easy Start (Windows)
If you have the source code folder:
1.  Double-click **`start_nepse.bat`**.
2.  That's it! It will check for Python, install dependencies, and launch the tool.

### Browser Setup
The CLI will automatically install Playwright browsers on first run if they're not already installed. If you prefer to install manually:
```powershell
playwright install chromium
```

## Usage

### Interactive Shell (Recommended)
Simply run `nepse` to enter the modern interactive shell:
```powershell
nepse
```
Once inside the shell, you **do not** need to type `nepse` again. Just type the command directly:
*   `stonk NABIL`
*   `ipo`
*   `apply`
*   `mktsum`

**Shell Features:**
*   **Command Palette**: Type `/` to search all available commands.
*   **Autocompletion**: Type commands and see suggestions.
*   **History**: Use Up/Down arrows to cycle through command history.
*   **Help**: Type `help` or `?` to see the command list.

### Direct Commands

#### Meroshare IPO Automation
```powershell
# Apply for IPO (headless by default - no browser window)
nepse apply

# Apply with browser window visible
nepse apply --gui

# Apply for ALL family members (multi-tab automation)
nepse apply-all

# Apply for all members with browser visible
nepse apply-all --gui

# Add or update a family member
nepse add-member

# List all family members
nepse list-members

# Get portfolio (headless by default)
nepse get-portfolio

# Get portfolio with browser window visible
nepse get-portfolio --gui

# Test login (headless by default)
nepse test-login

# Test login with browser window visible
nepse test-login --gui

# View available DP list
nepse dplist
```

#### Market Data Commands
```powershell
# View all open IPOs/FPOs
nepse ipo

# View NEPSE indices
nepse nepse

# View sub-index details (Banking, Hydropower, etc.)
nepse subidx BANKING
nepse subidx HYDROPOWER

# View market summary
nepse mktsum

# View top 10 gainers and losers
nepse topgl

# View stock details (information only - no charts)
nepse stonk NABIL
nepse stonk NICA
```

## Features

### 🖥️ Modern UI & UX
- **Rich TUI**: Beautiful tables, panels, and colored output for all commands.
- **Interactive Menus**: Select family members using arrow keys (no more typing IDs!).
- **Smart Shell**: Autocompletion, fuzzy search, and command history.
- **Progress Bars**: Visual feedback for all long-running operations.

### 🤖 Meroshare Automation
- ✅ **Multi-member Support**: Manage credentials for the whole family.
- ✅ **One-Command Apply**: `nepse apply-all` applies for everyone in sequence.
- ✅ **Interactive Selection**: Choose a specific member from a list using arrow keys.
- ✅ **Headless Mode**: Fast and silent operation by default.
- ✅ **Secure Storage**: Credentials stored locally in your user directory.

### 📈 Market Data
- ✅ **Live Indices**: NEPSE, Sensitive, Float, and Sub-indices.
- ✅ **Market Summary**: Turnover, volume, market cap, and active stocks.
- ✅ **Top Gainers/Losers**: Real-time lists of best and worst performers.
- ✅ **Stock Details**: Price, volume, sector, and changes for any listed company.
- ✅ **IPO Watch**: List of all open and upcoming IPOs/FPOs/Right Shares.

## Configuration

All credential data is stored in a **fixed location** to avoid path issues:

📁 **Data Directory**: `C:\Users\%USERNAME%\Documents\merosharedata\`

Files stored here:
- `family_members.json` - All family member credentials
- `ipo_config.json` - IPO application settings (if any)
- `nepse_cli_history.txt` - Command history for the interactive shell

This means the CLI works from **any directory** - your data is always in the same place!

Family member data structure:

```json
{
  "members": [
    {
      "name": "Dad",
      "dp_value": "139",
      "username": "your_username",
      "password": "your_password",
      "transaction_pin": "1234",
      "applied_kitta": 10,
      "crn_number": "YOUR_CRN"
    }
  ]
}
```

## Security

- Passwords are stored locally in JSON format
- File permissions are set to 600 on Unix systems
- Never commit `family_members.json` to version control

## Troubleshooting

**Command not found:**
- Make sure you ran `pip install -e .` in the Nepse CLI directory
- Restart your terminal after installation

**Browser not installed:**
- Run: `playwright install chromium`

**Login fails:**
- Test with: `nepse test-login`
- Verify credentials with: `nepse list-members`
- Update credentials with: `nepse add-member`
