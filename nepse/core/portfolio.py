"""
Portfolio Module.
Handles fetching and displaying portfolio data from Meroshare using direct API calls.
"""

import json
import time
from typing import Dict, List, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ..utils.formatting import format_rupees, format_number

console = Console(force_terminal=True, legacy_windows=False)

# ==========================================
# Constants
# ==========================================
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"
MS_API_BASE = "https://webbackend.cdsc.com.np/api"

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/json",
    "Origin": "https://meroshare.cdsc.com.np",
    "Connection": "keep-alive",
    "Referer": "https://meroshare.cdsc.com.np/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}


# ==========================================
# Errors
# ==========================================
class LocalException(Exception):
    """Local exception for portfolio operations."""
    def __init__(self, message: str):
        self.message = message
    
    def __str__(self):
        return self.message


class GlobalError(Exception):
    """Global error for critical failures."""
    def __init__(self, message: str):
        self.message = message
    
    def __str__(self):
        return self.message


# ==========================================
# Portfolio Models
# ==========================================
class PortfolioEntry:
    """Represents a single portfolio holding."""
    
    def __init__(self, **kwargs):
        self.current_balance = float(kwargs.get("currentBalance", 0))
        self.last_transaction_price = float(kwargs.get("lastTransactionPrice", 0))
        self.previous_closing_price = float(kwargs.get("previousClosingPrice", 0))
        self.script = kwargs.get("script", "")
        self.script_desc = kwargs.get("scriptDesc", "")
        self.value_as_of_last_transaction_price = float(kwargs.get("valueAsOfLastTransactionPrice", 0))
        self.value_as_of_previous_closing_price = float(kwargs.get("valueAsOfPreviousClosingPrice", 0))

    def to_json(self):
        return {
            "current_balance": self.current_balance,
            "last_transaction_price": self.last_transaction_price,
            "previous_closing_price": self.previous_closing_price,
            "script": self.script,
            "script_desc": self.script_desc,
            "value_as_of_last_transaction_price": self.value_as_of_last_transaction_price,
            "value_as_of_previous_closing_price": self.value_as_of_previous_closing_price,
        }


class Portfolio:
    """Represents complete portfolio data."""
    
    def __init__(self, entries, total_items, total_val_ltp, total_val_prev):
        self.entries = entries
        self.total_items = total_items
        self.total_value_as_of_last_transaction_price = total_val_ltp
        self.total_value_as_of_previous_closing_price = total_val_prev

    def to_json(self):
        return {
            "entries": [entry.to_json() for entry in self.entries],
            "total_items": self.total_items,
            "total_value_as_of_last_transaction_price": self.total_value_as_of_last_transaction_price,
            "total_value_as_of_previous_closing_price": self.total_value_as_of_previous_closing_price,
        }


# ==========================================
# Helper Functions
# ==========================================
def fetch_capital_id(dpid_code: str) -> int:
    """
    Fetch Capital ID from DPID Code (e.g. '10900' -> 190).
    
    Args:
        dpid_code: The DPID code to lookup
        
    Returns:
        Capital ID integer
    """
    console.print(f'[cyan]🔍 Looking up Capital ID for DPID:[/cyan] {dpid_code}')
    
    try:
        response = requests.get(f"{MS_API_BASE}/meroShare/capital/", headers=BASE_HEADERS)
        if response.status_code == 200:
            capitals = response.json()
            for cap in capitals:
                if cap.get('code') == str(dpid_code):
                    console.print(f"[green]✓ Found Capital:[/green] {cap.get('name')} (ID: {cap.get('id')})")
                    return cap.get('id')
    except Exception as e:
        console.print(f"[red]✗ Error fetching capitals:[/red] {e}")
    
    raise GlobalError(f"Could not find Capital ID for DPID {dpid_code}")


# ==========================================
# Account Class
# ==========================================
class Account:
    """Handles Meroshare account operations via direct API calls."""
    
    def __init__(self, username: str, password: str, dpid_code: str, capital_id: int):
        """
        Initialize account.
        
        Args:
            username: Meroshare username
            password: Meroshare password
            dpid_code: DPID code (e.g. "10900")
            capital_id: Capital ID integer
        """
        self.username = username
        self.password = password
        self.dpid_code = dpid_code
        self.capital_id = capital_id
        
        self.dmat = None
        self.name = None
        self.auth_token = None
        self.portfolio = None

        self.__session = requests.Session()
        self.__session.headers.update(BASE_HEADERS)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def login(self) -> str:
        """
        Perform login and get auth token.
        
        Returns:
            Authorization token string
        """
        data = {
            "clientId": str(self.capital_id),
            "username": self.username,
            "password": self.password,
        }

        headers = BASE_HEADERS.copy()
        headers["Authorization"] = "null"
        headers["Content-Type"] = "application/json"

        with console.status("[bold green]Logging in...", spinner="dots"):
            login_req = requests.post(f"{MS_API_BASE}/meroShare/auth/", json=data, headers=headers)
            
            if login_req.status_code != 200:
                raise LocalException(f"Login failed with status {login_req.status_code}")

            self.auth_token = login_req.headers.get("Authorization")
            self.__session.headers.update({"Authorization": self.auth_token})
        
        console.print('[bold green]✓ Login successful[/bold green]')
        return self.auth_token

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_own_details(self):
        """
        Fetch user details to get Demat number and name.
        
        Returns:
            Dict with user details
        """
        console.print('[cyan]👤 Fetching account details...[/cyan]')
        
        headers = BASE_HEADERS.copy()
        headers["Authorization"] = self.auth_token
        
        response = requests.get(f"{MS_API_BASE}/meroShare/ownDetail/", headers=headers)

        if response.status_code == 200:
            data = response.json()
            self.dmat = data.get('demat')
            self.name = data.get('name')
            console.print(f'[green]✓ Account:[/green] {self.name}')
            console.print(f'[green]✓ Demat:[/green] {self.dmat}')
            return data
        else:
            raise LocalException(f"Failed to fetch own details: {response.status_code}")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_portfolio(self) -> Portfolio:
        """
        Fetch portfolio holdings.
        
        Returns:
            Portfolio object with holdings
        """
        if not self.dmat:
            self.fetch_own_details()
        
        with console.status("[bold green]Fetching portfolio...", spinner="dots"):
            headers = BASE_HEADERS.copy()
            headers["Authorization"] = self.auth_token
            headers["Content-Type"] = "application/json"
            
            payload = {
                "sortBy": "script",
                "demat": [self.dmat],
                "clientCode": self.dpid_code, 
                "page": 1,
                "size": 200,
                "sortAsc": True,
            }
            
            portfolio_req = requests.post(
                f"{MS_API_BASE}/meroShareView/myPortfolio/",
                json=payload,
                headers=headers
            )

            if portfolio_req.status_code != 200:
                raise LocalException(f"Portfolio request failed with status {portfolio_req.status_code}")

            data = portfolio_req.json()
            
            entries = [PortfolioEntry(**item) for item in data.get("meroShareMyPortfolio", [])]
            
            new_portfolio = Portfolio(
                entries=entries,
                total_items=data.get("totalItems"),
                total_val_ltp=float(data.get("totalValueAsOfLastTransactionPrice", 0)),
                total_val_prev=float(data.get("totalValueAsOfPreviousClosingPrice", 0)),
            )

            self.portfolio = new_portfolio
        
        console.print('[bold green]✓ Portfolio fetched successfully[/bold green]\n')
        return new_portfolio

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_wacc_report(self):
        """
        Fetch WACC report from myPurchase API.
        
        Returns:
            WACC report data
        """
        if not self.dmat:
            self.fetch_own_details()

        console.print('[cyan]📊 Fetching WACC report...[/cyan]')
        
        headers = BASE_HEADERS.copy()
        headers["Authorization"] = self.auth_token
        headers["Content-Type"] = "application/json"

        payload = {"demat": self.dmat}

        wacc_req = requests.post(
            f"{MS_API_BASE}/myPurchase/waccReport/",
            json=payload,
            headers=headers,
        )

        if wacc_req.status_code != 200:
            raise LocalException(f"WACC report request failed: {wacc_req.status_code}")

        console.print('[green]✓ WACC report fetched[/green]')
        return wacc_req.json()



class PortfolioFetcher:
    """Handles portfolio fetching operations."""
    
    def __init__(self, member: Dict):
        """
        Initialize with member credentials.
        
        Args:
            member: Dict with dp_value, username, password keys
        """
        self.member = member
        self.account = None
    
    def fetch(self) -> Optional[Portfolio]:
        """
        Fetch portfolio holdings using direct API.
        
        Returns:
            Portfolio object or None if failed
        """
        try:
            # Extract DPID code from dp_value or member dict
            dp_value = self.member.get('dp_value', '')
            dpid_code = self.member.get('dpid_code')
            
            # Try to extract from dp_value if dpid_code not provided
            if not dpid_code and dp_value:
                # Try to extract numeric portion
                import re
                match = re.search(r'\((\d+)\)', dp_value)
                if match:
                    dpid_code = match.group(1)
                elif dp_value.isdigit():
                    dpid_code = dp_value
            
            if not dpid_code:
                console.print("[red]✗ Could not determine DPID code[/red]")
                return None
            
            # Get capital ID
            capital_id = fetch_capital_id(dpid_code)
            
            # Create account and login
            self.account = Account(
                username=self.member['username'],
                password=self.member['password'],
                dpid_code=dpid_code,
                capital_id=capital_id
            )
            
            self.account.login()
            time.sleep(0.5)
            
            self.account.fetch_own_details()
            time.sleep(0.5)
            
            portfolio = self.account.fetch_portfolio()
            
            return portfolio
            
        except Exception as e:
            console.print(f"[red]⚠ Error fetching portfolio: {e}[/red]")
            return None


def display_portfolio_table(member_name: str, portfolio: Portfolio) -> Table:
    """
    Create a Rich table for portfolio display.
    
    Args:
        member_name: Name of the member
        portfolio: Portfolio object with holdings
        
    Returns:
        Rich Table object
    """
    table = Table(
        title=f"💼 PORTFOLIO: {member_name.upper()}", 
        box=box.ROUNDED, 
        header_style="bold cyan", 
        expand=True,
        show_lines=True
    )
    
    table.add_column("#", style="dim", width=4, justify="center")
    table.add_column("Symbol", style="bold yellow", width=12)
    table.add_column("Company", style="white")
    table.add_column("Shares", justify="right", style="cyan")
    table.add_column("LTP", justify="right", style="magenta")
    table.add_column("Prev. Close", justify="right", style="dim")
    table.add_column("Value (LTP)", justify="right", style="bold green")
    
    for idx, entry in enumerate(portfolio.entries, 1):
        # Truncate company name if too long
        company_name = entry.script_desc
        if len(company_name) > 50:
            company_name = company_name[:47] + "..."
        
        table.add_row(
            str(idx),
            entry.script,
            company_name,
            format_number(entry.current_balance),
            format_rupees(entry.last_transaction_price),
            format_rupees(entry.previous_closing_price),
            format_rupees(entry.value_as_of_last_transaction_price)
        )
    
    # Add totals row
    table.add_section()
    table.add_row(
        "",
        "[bold]TOTAL[/bold]", 
        f"[bold]{portfolio.total_items} scrips[/bold]",
        "",
        "",
        "",
        f"[bold]{format_rupees(portfolio.total_value_as_of_last_transaction_price)}[/bold]",
        style="bold bright_white"
    )
    
    return table


def display_portfolio_summary(member_name: str, portfolio: Portfolio) -> Panel:
    """
    Create a summary panel for portfolio.
    
    Args:
        member_name: Name of the member
        portfolio: Portfolio object
        
    Returns:
        Rich Panel with summary
    """
    summary_text = f"""
[cyan]Account:[/cyan] [bold white]{member_name}[/bold white]
[cyan]Total Holdings:[/cyan] [bold]{portfolio.total_items}[/bold] scrips
[cyan]Portfolio Value:[/cyan] [bold green]{format_rupees(portfolio.total_value_as_of_last_transaction_price)}[/bold green]
[cyan]Previous Value:[/cyan] {format_rupees(portfolio.total_value_as_of_previous_closing_price)}
"""
    
    return Panel(
        summary_text.strip(),
        title="📊 Portfolio Summary",
        border_style="green",
        box=box.ROUNDED
    )


def save_portfolio_to_file(portfolio: Portfolio, member_name: str = "", filename: str = None) -> None:
    """
    Save portfolio data to JSON file.
    
    Args:
        portfolio: Portfolio object
        member_name: Name of member (for filename)
        filename: Custom filename (optional)
    """
    if not filename:
        safe_name = member_name.replace(" ", "_").lower()
        filename = f"portfolio_{safe_name}_{int(time.time())}.json"
    
    output = {
        "fetched_at": time.strftime("%Y-%m-%d %I:%M:%S %p"),
        "member_name": member_name,
        "portfolio": portfolio.to_json()
    }
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    console.print(f"[dim]💾 Portfolio data saved to: {filename}[/dim]\n")


def get_portfolio_for_member(member: Dict, save_to_file: bool = False, headless: bool = True) -> Optional[Portfolio]:
    """
    Get portfolio for a specific family member using direct API.
    
    Args:
        member: Member dictionary with credentials
        save_to_file: Whether to save portfolio to file (default: False)
        headless: Kept for backward compatibility (no longer used since we use direct API)
        
    Returns:
        Portfolio object or None if failed
    """
    console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
    console.print(f"[bold white]Fetching Portfolio for: {member['name']}[/bold white]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
    
    fetcher = PortfolioFetcher(member)
    portfolio = fetcher.fetch()
    
    if portfolio:
        # Display summary panel
        summary_panel = display_portfolio_summary(member['name'], portfolio)
        console.print(summary_panel)
        console.print()
        
        # Display detailed table
        table = display_portfolio_table(member['name'], portfolio)
        console.print(table)
        console.print()
        
        # Save to file (optional)
        if save_to_file:
            save_portfolio_to_file(portfolio, member['name'])
        
        return portfolio
    else:
        console.print("[yellow]⚠ No portfolio data found.[/yellow]")
        return None
