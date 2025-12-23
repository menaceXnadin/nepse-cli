"""
Market Data Service.
Handles fetching and displaying NEPSE market data from various APIs.
"""

import time
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich import box

from ..utils.formatting import format_number, format_rupees

console = Console(force_terminal=True, legacy_windows=False)


def get_ss_time() -> str:
    """Get timestamp from ShareSansar market summary."""
    try:
        response = requests.get("https://www.sharesansar.com/market-summary", timeout=10)
        soup = BeautifulSoup(response.text, "lxml")
        summary_cont = soup.find("div", id="market_symmary_data")
        if summary_cont is not None:
            msdate = summary_cont.find("h5").find("span")
            if msdate is not None:
                return msdate.text
    except:
        pass
    return "N/A"


def cmd_ipo() -> None:
    """Display all open IPOs/public offerings."""
    try:
        with console.status("[bold green]Fetching open IPOs...", spinner="dots"):
            response = requests.get(
                "https://sharehubnepal.com/data/api/v1/public-offering",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        
        if not data.get('success'):
            console.print(Panel(
                "⚠️  Unable to fetch IPO data. API request failed.",
                style="bold red",
                box=box.ROUNDED
            ))
            return
        
        all_ipos = data.get('data', {}).get('content', [])
        
        def _is_general_public(ipo_item):
            try:
                f = str(ipo_item.get('for', '')).lower()
            except Exception:
                return False
            return 'general' in f and 'public' in f
        
        open_ipos = [
            ipo for ipo in all_ipos 
            if ipo.get('status') == 'Open' and _is_general_public(ipo)
        ]
        
        if not open_ipos:
            console.print(Panel(
                "💤 No IPOs are currently open for subscription.",
                style="bold yellow",
                box=box.ROUNDED
            ))
            return
        
        table = Table(
            title=f"📈 Open IPOs ({len(open_ipos)})",
            box=box.ROUNDED,
            header_style="bold cyan",
            expand=True
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Company", style="bold white")
        table.add_column("Type", style="cyan")
        table.add_column("Units", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Closing", style="yellow")
        table.add_column("Status", justify="center")
        
        for index, ipo in enumerate(open_ipos, 1):
            symbol = ipo.get('symbol', 'N/A')
            name = ipo.get('name', 'N/A')
            units = ipo.get('units', 0)
            price = ipo.get('price', 0)
            closing_date = ipo.get('closingDate', 'N/A')
            extended_closing = ipo.get('extendedClosingDate', None)
            ipo_type = ipo.get('type', 'N/A')
            
            try:
                closing_date_obj = datetime.fromisoformat(closing_date.replace('T', ' '))
                closing_date_str = closing_date_obj.strftime('%d %b')
            except:
                closing_date_str = closing_date
            
            # Calculate urgency
            urgency_text = ""
            urgency_style = "white"
            
            try:
                target_date = extended_closing if extended_closing else closing_date
                target_date_obj = datetime.fromisoformat(target_date.replace('T', ' '))
                days_left = (target_date_obj - datetime.now()).days
                
                if days_left >= 0:
                    if days_left <= 2:
                        urgency_text = f"⚠️ {days_left}d left"
                        urgency_style = "bold red"
                    elif days_left <= 5:
                        urgency_text = f"⏰ {days_left}d left"
                        urgency_style = "yellow"
                    else:
                        urgency_text = f"📅 {days_left}d"
                        urgency_style = "green"
            except:
                urgency_text = "Check dates"
            
            type_emojis = {
                'Ipo': '🆕 IPO',
                'Right': '🔄 Right',
                'MutualFund': '💼 MF',
                'BondOrDebenture': '💰 Bond'
            }
            type_display = type_emojis.get(ipo_type, ipo_type)
            
            table.add_row(
                str(index),
                f"{symbol}\n[dim]{name}[/dim]",
                type_display,
                f"{units:,}",
                format_rupees(price),
                closing_date_str,
                f"[{urgency_style}]{urgency_text}[/{urgency_style}]"
            )
        
        console.print(table)
        console.print(Panel(
            "💡 Tip: Use [bold cyan]apply[/] to apply for IPO via Meroshare",
            box=box.ROUNDED,
            style="dim"
        ))
        
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]🔌 Connection Error:[/bold red] {str(e)[:100]}\n")
    except Exception as e:
        console.print(f"[bold red]⚠️  Error:[/bold red] {str(e)[:200]}\n")


def cmd_nepse() -> None:
    """Display NEPSE indices data."""
    try:
        with console.status("[bold green]Fetching NEPSE indices...", spinner="dots"):
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            
            url = "https://nepsealpha.com/live/stocks"
            response = scraper.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Fetch ShareHub data
            market_status = "UNKNOWN"
            market_summary = None
            stock_summary = None
            try:
                sharehub_response = requests.get(
                    "https://sharehubnepal.com/live/api/v2/nepselive/home-page-data",
                    timeout=10
                )
                if sharehub_response.status_code == 200:
                    sharehub_data = sharehub_response.json()
                    market_status_obj = sharehub_data.get('marketStatus', {})
                    market_status = market_status_obj.get('status', 'UNKNOWN')
                    market_summary = sharehub_data.get('marketSummary', [])
                    stock_summary = sharehub_data.get('stockSummary', {})
            except:
                pass
        
        prices = data.get('stock_live', {}).get('prices', [])
        indices = [item for item in prices if item.get('stockinfo', {}).get('type') == 'index']
        
        if not indices:
            console.print(Panel(
                "⚠️  No index data available.",
                style="bold yellow",
                box=box.ROUNDED
            ))
            return
        
        timestamp = data.get('stock_live', {}).get('asOf', 'N/A')
        
        # Market status indicator
        if market_status == "OPEN":
            status_indicator = "[bold green]●[/bold green] OPEN"
            status_color = "green"
        elif market_status == "CLOSE":
            status_indicator = "[bold red]●[/bold red] CLOSE"
            status_color = "red"
        else:
            status_indicator = "[bold yellow]●[/bold yellow] UNKNOWN"
            status_color = "yellow"
        
        # Separate main and sub indices
        main_index_names = ['NEPSE', 'SENSITIVE', 'FLOAT', 'SENFLOAT']
        main_indices = [item for item in indices if item.get('symbol', '') in main_index_names]
        sub_indices = [item for item in indices if item.get('symbol', '') not in main_index_names]
        
        main_order = {name: idx for idx, name in enumerate(main_index_names)}
        main_indices.sort(key=lambda x: main_order.get(x.get('symbol', ''), 999))
        
        # Main Indices Table
        main_table = Table(
            title=f"📊 Main Indices (Live) - {timestamp} | Market: {status_indicator}",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style=status_color
        )
        main_table.add_column("Index", style="bold white", width=16)
        main_table.add_column("Open", justify="right")
        main_table.add_column("Close", justify="right")
        main_table.add_column("Change", justify="right")
        main_table.add_column("% Change", justify="right")
        main_table.add_column("Trend", justify="center")
        main_table.add_column("Range (L-H)", justify="center", style="dim")
        main_table.add_column("Turnover", justify="right")
        
        for item in main_indices:
            index_name = item.get('symbol', 'N/A')
            open_val = item.get('open', 0)
            close_val = item.get('close', 0)
            pct_change = item.get('percent_change', 0)
            low_val = item.get('low', 0)
            high_val = item.get('high', 0)
            turnover = item.get('volume', 0)
            
            try:
                if pct_change != 0 and close_val != 0:
                    prev_close = close_val / (1 + pct_change / 100)
                    point_change = close_val - prev_close
                else:
                    point_change = 0
            except:
                point_change = 0
            
            color = "green" if pct_change > 0 else "red" if pct_change < 0 else "yellow"
            trend_icon = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "•"
            range_str = f"{low_val:,.2f} - {high_val:,.2f}"
            
            main_table.add_row(
                index_name,
                f"{open_val:,.2f}",
                f"{close_val:,.2f}",
                f"[{color}]{point_change:+,.2f}[/{color}]",
                f"[{color}]{pct_change:+.2f}%[/{color}]",
                f"[{color}]{trend_icon}[/{color}]",
                range_str,
                format_number(turnover)
            )
        
        console.print(main_table)
        
        # Market Overview
        if market_summary:
            console.print("\n")
            market_table = Table(
                title="💰 Market Overview",
                box=box.ROUNDED,
                header_style="bold cyan",
                border_style="cyan"
            )
            
            for item in market_summary:
                metric_name = item.get('name', 'N/A')
                short_name = metric_name.replace('Total ', '').replace(' Rs:', '').replace(':', '')
                market_table.add_column(short_name, justify="right", style="cyan")
            
            row_values = []
            for item in market_summary:
                metric_value = item.get('value', 0)
                metric_name = item.get('name', 'N/A')
                
                if 'Turnover' in metric_name:
                    formatted_value = f"Rs. {metric_value:,.2f}"
                elif any(x in metric_name for x in ['Shares', 'Transactions', 'Scripts']):
                    formatted_value = f"{int(metric_value):,}"
                else:
                    formatted_value = f"{metric_value:,}"
                
                row_values.append(formatted_value)
            
            market_table.add_row(*row_values)
            console.print(market_table)
        
        # Stock Movement
        if stock_summary:
            console.print("\n")
            stock_table = Table(
                title="📊 Stock Movement",
                box=box.ROUNDED,
                header_style="bold magenta",
                border_style="magenta"
            )
            
            stock_table.add_column("Advanced", justify="center", style="bold green")
            stock_table.add_column("Declined", justify="center", style="bold red")
            stock_table.add_column("Unchanged", justify="center", style="bold yellow")
            stock_table.add_column("Positive Circuit", justify="center")
            stock_table.add_column("Negative Circuit", justify="center")
            
            advanced = stock_summary.get('advanced', 0)
            declined = stock_summary.get('declined', 0)
            unchanged = stock_summary.get('unchanged', 0)
            positive_circuit = stock_summary.get('positiveCircuit', 0)
            negative_circuit = stock_summary.get('negativeCircuit', 0)
            
            pos_circuit_color = "bright_green" if positive_circuit > 0 else "dim"
            neg_circuit_color = "bright_red" if negative_circuit > 0 else "dim"
            
            stock_table.add_row(
                f"{advanced:,}",
                f"{declined:,}",
                f"{unchanged:,}",
                f"[{pos_circuit_color}]{positive_circuit:,}[/{pos_circuit_color}]",
                f"[{neg_circuit_color}]{negative_circuit:,}[/{neg_circuit_color}]"
            )
            
            console.print(stock_table)
        
        # Sub-Indices
        if sub_indices:
            console.print("\n")
            sub_table = Table(
                title="📈 Sub-Indices",
                box=box.ROUNDED,
                header_style="bold magenta"
            )
            sub_table.add_column("Index", style="bold white")
            sub_table.add_column("Close", justify="right")
            sub_table.add_column("Change", justify="right")
            sub_table.add_column("% Change", justify="right")
            sub_table.add_column("Trend", justify="center")
            sub_table.add_column("Range (L-H)", justify="center", style="dim")
            
            for item in sub_indices:
                index_name = item.get('symbol', 'N/A')
                close_val = item.get('close', 0)
                pct_change = item.get('percent_change', 0)
                low_val = item.get('low', 0)
                high_val = item.get('high', 0)
                
                try:
                    if pct_change != 0 and close_val != 0:
                        prev_close = close_val / (1 + pct_change / 100)
                        point_change = close_val - prev_close
                    else:
                        point_change = 0
                except:
                    point_change = 0
                
                color = "green" if pct_change > 0 else "red" if pct_change < 0 else "yellow"
                trend_icon = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "•"
                range_str = f"{low_val:,.2f} - {high_val:,.2f}"
                
                sub_table.add_row(
                    index_name,
                    f"{close_val:,.2f}",
                    f"[{color}]{point_change:+,.2f}[/{color}]",
                    f"[{color}]{pct_change:+.2f}%[/{color}]",
                    f"[{color}]{trend_icon}[/{color}]",
                    range_str
                )
            
            console.print(sub_table)
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error fetching NEPSE data:[/bold red] {str(e)}\n")


def cmd_subidx(subindex_name: str) -> None:
    """Display sub-index details."""
    try:
        subindex_name = subindex_name.upper()
        
        sub_index_mapping = {
            "BANKING": "BANKING",
            "DEVBANK": "DEVBANK",
            "FINANCE": "FINANCE",
            "HOTELS AND TOURISM": "HOTELS",
            "HOTELS": "HOTELS",
            "HYDROPOWER": "HYDROPOWER",
            "INVESTMENT": "INVESTMENT",
            "LIFE INSURANCE": "LIFEINSU",
            "LIFEINSU": "LIFEINSU",
            "MANUFACTURING AND PROCESSING": "MANUFACTURE",
            "MANUFACTURE": "MANUFACTURE",
            "MICROFINANCE": "MICROFINANCE",
            "MUTUAL FUND": "MUTUAL",
            "MUTUAL": "MUTUAL",
            "NONLIFE INSURANCE": "NONLIFEINSU",
            "NONLIFEINSU": "NONLIFEINSU",
            "OTHERS": "OTHERS",
            "TRADING": "TRADING",
        }
        
        with console.status(f"[bold green]Fetching {subindex_name} data...", spinner="dots"):
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            response = scraper.get("https://nepsealpha.com/live/stocks", timeout=10)
            response.raise_for_status()
            data = response.json()
        
        search_symbol = sub_index_mapping.get(subindex_name, subindex_name)
        
        prices = data.get('stock_live', {}).get('prices', [])
        indices = [item for item in prices if item.get('stockinfo', {}).get('type') == 'index']
        
        sub_index_data = None
        for item in indices:
            if item.get('symbol', '').upper() == search_symbol.upper():
                sub_index_data = item
                break
        
        if not sub_index_data:
            console.print(Panel(
                f"⚠️  Sub-index '{subindex_name}' not found.",
                style="bold red",
                box=box.ROUNDED
            ))
            
            available = set()
            for item in indices:
                symbol = item.get('symbol', '')
                if symbol not in ['NEPSE', 'SENSITIVE', 'FLOAT']:
                    available.add(symbol)
            
            table = Table(title="Available Sub-Indices", box=box.ROUNDED)
            table.add_column("Symbol", style="cyan")
            for sym in sorted(available):
                table.add_row(sym)
            console.print(table)
            return
        
        sectors = data.get('sectors', {})
        sector_full_name = sectors.get(search_symbol, search_symbol)
        
        close_val = sub_index_data.get('close', 0)
        pct_change = sub_index_data.get('percent_change', 0)
        low_val = sub_index_data.get('low', 0)
        high_val = sub_index_data.get('high', 0)
        open_val = sub_index_data.get('open', 0)
        turnover = sub_index_data.get('volume', 0)
        
        try:
            if pct_change != 0 and close_val != 0:
                prev_close = close_val / (1 + pct_change / 100)
                point_change = close_val - prev_close
            else:
                point_change = 0
        except:
            point_change = 0
        
        color = "green" if pct_change > 0 else "red" if pct_change < 0 else "yellow"
        trend_icon = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "•"
        
        timestamp = data.get('stock_live', {}).get('asOf', 'N/A')
        
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(style="bold white")
        grid.add_column(justify="right")
        
        grid.add_row("Close Price", f"{close_val:,.2f}")
        grid.add_row("Change", f"[{color}]{point_change:+,.2f} ({pct_change:+.2f}%)[/{color}]")
        grid.add_row("Trend", f"[{color}]{trend_icon} {color.upper()}[/{color}]")
        grid.add_row("Range (Low-High)", f"{low_val:,.2f} - {high_val:,.2f}")
        grid.add_row("Open Price", f"{open_val:,.2f}")
        grid.add_row("Turnover", format_number(turnover))
        
        panel = Panel(
            grid,
            title=f"[bold {color}]{sector_full_name} ({search_symbol})[/]",
            subtitle=f"As of: {timestamp}",
            box=box.ROUNDED,
            border_style=color
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error fetching sub-index data:[/bold red] {str(e)}\n")


def cmd_topgl() -> None:
    """Display top 10 gainers and losers."""
    try:
        with console.status("[bold green]Fetching top gainers and losers...", spinner="dots"):
            response = requests.get("https://merolagani.com/LatestMarket.aspx", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tgtl_col = soup.find('div', class_="col-md-4 hidden-xs hidden-sm")
            tgtl_tables = tgtl_col.find_all('table')
            
            gainers = tgtl_tables[0]
            gainers_row = gainers.find_all('tr')
            
            losers = tgtl_tables[1]
            losers_row = losers.find_all('tr')
        
        # Gainers Table
        g_table = Table(
            title="📈 TOP 10 GAINERS",
            box=box.ROUNDED,
            header_style="bold green",
            expand=True
        )
        g_table.add_column("#", style="dim", width=4)
        g_table.add_column("Symbol", style="bold white")
        g_table.add_column("LTP", justify="right")
        g_table.add_column("%Chg", justify="right", style="green")
        g_table.add_column("High", justify="right", style="dim")
        g_table.add_column("Low", justify="right", style="dim")
        g_table.add_column("Volume", justify="right")
        
        for idx, tr in enumerate(gainers_row[1:], 1):
            tds = tr.find_all('td')
            if tds and len(tds) >= 8:
                medal = ["🥇", "🥈", "🥉"] + [""] * 7
                g_table.add_row(
                    f"{idx} {medal[idx-1]}",
                    tds[0].text,
                    tds[1].text,
                    f"+{tds[2].text}%",
                    tds[3].text,
                    tds[4].text,
                    format_number(tds[6].text)
                )
        
        # Losers Table
        l_table = Table(
            title="📉 TOP 10 LOSERS",
            box=box.ROUNDED,
            header_style="bold red",
            expand=True
        )
        l_table.add_column("#", style="dim", width=4)
        l_table.add_column("Symbol", style="bold white")
        l_table.add_column("LTP", justify="right")
        l_table.add_column("%Chg", justify="right", style="red")
        l_table.add_column("High", justify="right", style="dim")
        l_table.add_column("Low", justify="right", style="dim")
        l_table.add_column("Volume", justify="right")
        
        for idx, tr in enumerate(losers_row[1:], 1):
            tds = tr.find_all('td')
            if tds and len(tds) >= 8:
                l_table.add_row(
                    str(idx),
                    tds[0].text,
                    tds[1].text,
                    f"-{tds[2].text}%",
                    tds[3].text,
                    tds[4].text,
                    format_number(tds[6].text)
                )
        
        console.print(g_table)
        console.print(l_table)
        
        timestamp = get_ss_time()
        console.print(f"[dim]As of: {timestamp}[/dim]\n", justify="center")
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error fetching top gainers/losers:[/bold red] {str(e)}\n")


def cmd_stonk(stock_names: str) -> None:
    """Display stock details for one or multiple stocks."""
    try:
        # Parse multiple stock names (space or comma separated)
        import re
        stock_list = re.split(r'[,\s]+', stock_names.strip())
        stock_list = [s.upper() for s in stock_list if s]
        
        if not stock_list:
            console.print("[red]⚠️  No stock symbols provided.[/red]")
            return
        
        with console.status(f"[bold green]Fetching {len(stock_list)} stock(s)...", spinner="dots"):
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            
            response = scraper.get('https://nepsealpha.com/live/stocks', timeout=10)
            response.raise_for_status()
            data = response.json()
            
            prices = data.get('stock_live', {}).get('prices', [])
            timestamp = data.get('stock_live', {}).get('asOf', 'N/A')
        
        # Find data for each requested stock
        found_stocks = []
        not_found = []
        
        for stock_name in stock_list:
            stock_data = None
            for item in prices:
                if item.get('symbol', '').upper() == stock_name:
                    stock_data = item
                    break
            
            if stock_data:
                found_stocks.append((stock_name, stock_data))
            else:
                not_found.append(stock_name)
        
        # Display each stock
        for idx, (stock_name, stock_price_data) in enumerate(found_stocks):
            close_price = stock_price_data.get("close", 0)
            percent_change = stock_price_data.get("percent_change", 0)
            
            try:
                if percent_change != 0 and close_price != 0:
                    prev_close = close_price / (1 + percent_change / 100)
                    pt_change = close_price - prev_close
                else:
                    prev_close = close_price
                    pt_change = 0
            except:
                prev_close = close_price
                pt_change = 0
            
            color = "green" if pt_change > 0 else "red" if pt_change < 0 else "yellow"
            trend_icon = "▲" if pt_change > 0 else "▼" if pt_change < 0 else "•"
            
            grid = Table.grid(expand=True, padding=(0, 2))
            grid.add_column(style="bold white")
            grid.add_column(justify="right")
            
            grid.add_row("Last Traded Price", f"Rs. {close_price:,.2f}")
            grid.add_row("Change", f"[{color}]{pt_change:+,.2f} ({percent_change:+.2f}%) {trend_icon}[/{color}]")
            grid.add_row("Open", f"Rs. {stock_price_data.get('open', 0):,.2f}")
            grid.add_row("High", f"Rs. {stock_price_data.get('high', 0):,.2f}")
            grid.add_row("Low", f"Rs. {stock_price_data.get('low', 0):,.2f}")
            grid.add_row("Volume", f"{int(stock_price_data.get('volume', 0)):,}")
            grid.add_row("Prev. Closing", f"Rs. {prev_close:,.2f}")
            
            panel = Panel(
                grid,
                title=f"[bold {color}]{stock_name}[/]",
                subtitle=f"As of: {timestamp}",
                box=box.ROUNDED,
                border_style=color
            )
            console.print(panel)
            
            # Add spacing between stocks, but not after the last one
            if idx < len(found_stocks) - 1:
                console.print()
        
        # Show not found stocks
        if not_found:
            console.print()
            console.print(Panel(
                f"⚠️  Stock(s) not found: {', '.join(not_found)}",
                style="bold yellow",
                box=box.ROUNDED
            ))
        
        # Show chart link for single stock
        if len(found_stocks) == 1:
            chart_url = f"https://nepsealpha.com/trading/chart?symbol={found_stocks[0][0]}"
            console.print(f"\n[dim]📊 View Chart:[/dim] [link={chart_url}][cyan underline]{chart_url}[/cyan underline][/link]\n")
        elif found_stocks:
            console.print("\n[dim]💡 Tip: Use 'stonk <symbol>' with a single stock to view chart link[/dim]\n")
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error fetching stock data:[/bold red] {str(e)}\n")


def cmd_mktsum() -> None:
    """Display comprehensive market summary."""
    try:
        sharehub_data = None
        
        with console.status("[bold green]Fetching market data...", spinner="dots"):
            try:
                url = "https://sharehubnepal.com/live/api/v2/nepselive/home-page-data"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    sharehub_data = response.json()
            except Exception as e:
                console.print(f"[red]⚠️  API request failed: {e}[/red]")
            
            if not sharehub_data:
                return
        
        indices = sharehub_data.get("indices", [])
        nepse_index = next((i for i in indices if i.get("symbol") == "NEPSE"), {})
        
        if not nepse_index:
            console.print("[red]⚠️  NEPSE index data not found.[/red]")
            return
        
        current_price = float(nepse_index.get('currentValue', 0))
        daily_gain = float(nepse_index.get('changePercent', 0))
        
        # Market summary
        turnover = 0
        total_traded_shares = 0
        total_transactions = 0
        
        market_summary = sharehub_data.get("marketSummary", [])
        for item in market_summary:
            name = item.get('name', '')
            value = item.get('value', 0)
            if 'Turnover' in name:
                turnover = float(value)
            elif 'Traded Shares' in name:
                total_traded_shares = int(value)
            elif 'Transactions' in name:
                total_transactions = int(value)
        
        # Stock summary
        stock_summary = sharehub_data.get("stockSummary", {})
        positive_stocks = stock_summary.get("advanced", 0)
        negative_stocks = stock_summary.get("declined", 0)
        unchanged_stocks = stock_summary.get("unchanged", 0)
        positive_circuit = stock_summary.get("positiveCircuit", 0)
        negative_circuit = stock_summary.get("negativeCircuit", 0)
        total_traded = positive_stocks + negative_stocks + unchanged_stocks
        
        color = "green" if daily_gain > 0 else "red" if daily_gain < 0 else "yellow"
        trend_icon = "▲" if daily_gain > 0 else "▼" if daily_gain < 0 else "•"
        
        # NEPSE Table
        nepse_table = Table(
            title="📊 NEPSE Index",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style=color
        )
        
        nepse_table.add_column("Current Index", justify="right", style="bold white")
        nepse_table.add_column("Daily Gain", justify="right")
        nepse_table.add_column("Turnover", justify="right", style="cyan")
        
        if total_traded_shares > 0:
            nepse_table.add_column("Traded Shares", justify="right", style="cyan")
        if total_transactions > 0:
            nepse_table.add_column("Transactions", justify="right", style="cyan")
        
        row_values = [
            f"{current_price:,.2f}",
            f"[{color}]{daily_gain:+.2f}% {trend_icon}[/{color}]",
            format_number(turnover)
        ]
        
        if total_traded_shares > 0:
            row_values.append(format_number(total_traded_shares))
        if total_transactions > 0:
            row_values.append(format_number(total_transactions))
        
        nepse_table.add_row(*row_values)
        console.print(nepse_table)
        
        # Trading Activity
        console.print("\n")
        activity_table = Table(
            title="📈 Trading Activity",
            box=box.ROUNDED,
            header_style="bold magenta",
            border_style="magenta"
        )
        
        activity_table.add_column("Positive Stocks", justify="center", style="bold green")
        activity_table.add_column("Negative Stocks", justify="center", style="bold red")
        activity_table.add_column("Unchanged", justify="center", style="bold yellow")
        activity_table.add_column("Positive Circuit", justify="center")
        activity_table.add_column("Negative Circuit", justify="center")
        activity_table.add_column("Total Traded", justify="center", style="bold white")
        
        pos_circuit_color = "bright_green" if positive_circuit > 0 else "dim"
        neg_circuit_color = "bright_red" if negative_circuit > 0 else "dim"
        
        activity_table.add_row(
            f"{positive_stocks:,}",
            f"{negative_stocks:,}",
            f"{unchanged_stocks:,}",
            f"[{pos_circuit_color}]{positive_circuit:,}[/{pos_circuit_color}]",
            f"[{neg_circuit_color}]{negative_circuit:,}[/{neg_circuit_color}]",
            f"{total_traded:,}"
        )
        
        console.print(activity_table)
        
        # Sector Performance
        sub_indices = sharehub_data.get("subIndices", [])
        if sub_indices:
            console.print("\n")
            sector_table = Table(
                title="Sector Performance",
                box=box.ROUNDED,
                expand=True
            )
            sector_table.add_column("Sector", style="cyan")
            sector_table.add_column("Current", justify="right")
            sector_table.add_column("Change %", justify="right")
            
            for sector in sub_indices:
                name = sector.get("name", "Unknown")
                price = sector.get("currentValue", 0)
                change = sector.get("changePercent", 0)
                
                sec_color = "green" if change > 0 else "red" if change < 0 else "white"
                
                sector_table.add_row(
                    name,
                    f"{price:,.2f}",
                    f"[{sec_color}]{change:+.2f}%[/{sec_color}]"
                )
            
            console.print(sector_table)
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error:[/bold red] {str(e)}\n")


def get_dp_list() -> None:
    """Fetch and display available DP list from API."""
    try:
        with console.status("[bold green]Fetching DP list...", spinner="dots"):
            response = requests.get("https://webbackend.cdsc.com.np/api/meroShare/capital/")
            response.raise_for_status()
            dp_data = response.json()
            dp_data.sort(key=lambda x: x['name'])
        
        table = Table(
            title=f"Available Depository Participants (Total: {len(dp_data)})",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        table.add_column("ID", style="bold yellow", justify="right")
        table.add_column("Code", style="dim")
        table.add_column("Name", style="white")
        
        for dp in dp_data:
            table.add_row(str(dp['id']), str(dp['code']), dp['name'])
        
        console.print(table)
        console.print(Panel(
            "Note: Use the [bold yellow]ID[/] when setting up credentials",
            box=box.ROUNDED,
            style="dim"
        ))
        
    except requests.RequestException as e:
        console.print(f"[bold red]✗ Error fetching DP list:[/bold red] {e}")
    except Exception as e:
        console.print(f"[bold red]✗ Unexpected error:[/bold red] {e}\n")
