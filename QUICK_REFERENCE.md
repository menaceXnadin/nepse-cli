# Nepse CLI - Quick Reference Card

## Interactive Shell (Recommended)

```bash
nepse
```
*   **Search**: Type `/` to search commands.
*   **Navigate**: Use Up/Down arrows for history.
*   **Select**: Use arrow keys for menus.

## Market Data Commands

```bash
# View all open IPOs/FPOs
nepse ipo

# View NEPSE indices (main, sensitive, float)
nepse nepse

# View sector sub-indices
nepse subidx BANKING          # Banking sector
nepse subidx HYDROPOWER       # Hydropower sector
nepse subidx FINANCE          # Finance sector
# ... and more (see full list below)

# View market summary (turnover, volume, market cap)
nepse mktsum

# View top 10 gainers and losers
nepse topgl

# View stock details (price, volume, sector, etc.)
nepse stonk NABIL             # Nabil Bank
nepse stonk NICA              # NIC Asia Bank
nepse stonk UPPER             # Upper Tamakoshi
# ... any valid stock symbol
```

## Available Sub-Indices

- `BANKING` - Banking SubIndex
- `DEVBANK` - Development Bank Index
- `FINANCE` - Finance Index
- `HOTELS AND TOURISM` - Hotels And Tourism
- `HYDROPOWER` - HydroPower Index
- `INVESTMENT` - Investment
- `LIFE INSURANCE` - Life Insurance
- `MANUFACTURING AND PROCESSING` - Manufacturing And Processing
- `MICROFINANCE` - Microfinance Index
- `MUTUAL FUND` - Mutual Fund
- `NONLIFE INSURANCE` - Non Life Insurance
- `OTHERS` - Others Index
- `TRADING` - Trading Index

## Meroshare IPO Automation

```bash
# Apply for IPO (single member)
nepse apply                   # Headless mode (default)
nepse apply --gui             # Show browser

# Apply for ALL family members
nepse apply-all               # Headless mode (default)
nepse apply-all --gui         # Show browser

# Manage family members
nepse add-member              # Add/update member
nepse list-members            # List all members

# Portfolio and login
nepse get-portfolio           # Get portfolio (headless)
nepse get-portfolio --gui     # Get portfolio (show browser)
nepse test-login              # Test login (headless)
nepse test-login --gui        # Test login (show browser)

# Utilities
nepse dplist                  # View available DPs
```

## Quick Tips

💡 **Interactive Selection:**
When running `nepse apply` or `nepse login`, use **Up/Down arrows** to select a family member from the list and press **Enter**.

💡 **Check IPO before applying:**
```bash
nepse ipo        # See what's open
nepse apply      # Apply for selected IPO
```

💡 **Market snapshot:**
```bash
nepse nepse      # Overall indices
nepse mktsum     # Market statistics
nepse topgl      # Best performers
```

💡 **Research a stock:**
```bash
nepse stonk NABIL     # Get stock info
nepse subidx BANKING  # Check sector trend
```

💡 **Monitor portfolio:**
```bash
nepse stonk <SYMBOL>  # Check stock price
nepse get-portfolio   # View holdings
```

## Notes

⚠️ **Internet Required:** All market data commands need internet connection

⚠️ **No Charts/Alerts:** Stock command shows info only (no chart generation or price alerts)

⚠️ **Real-time Data:** Data is fetched in real-time from ShareSansar, MeroLagani, and NepseAlpha

✅ **Fast & Lightweight:** Terminal-based, no GUI overhead

✅ **Multi-source:** Uses multiple APIs for reliability

## Data Sources

- 📊 **IPO Data:** ShareHub Nepal API
- 📈 **Indices:** ShareSansar
- 💰 **Market Summary:** ShareSansar
- 🏆 **Top G/L:** MeroLagani
- 📉 **Stock Prices:** NepseAlpha API (primary), ShareSansar (fallback)

## Installation

```bash
# Install CLI globally
cd "Nepse CLI"
pip install -e .

# Install dependencies
pip install -r requirements-playwright.txt

# Install browser for automation
playwright install chromium
```

## Help

```bash
# General help
nepse --help

# Command-specific help
nepse apply --help
nepse subidx --help
nepse stonk --help
```

## Examples

### Check market before trading:
```bash
nepse mktsum     # Market overview
nepse topgl      # See trends
nepse stonk UPPER # Check specific stock
```

### Research IPO:
```bash
nepse ipo              # See open IPOs
nepse subidx BANKING   # Check sector performance
nepse apply            # Apply if interested
```

### Monitor portfolio:
```bash
nepse portfolio        # View holdings
nepse stonk NABIL     # Check stock price
nepse nepse           # Overall market trend
```

---

**Need more help?** Check `README.md` and `MARKET_DATA_USAGE.md` for detailed documentation.
