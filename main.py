from playwright.sync_api import sync_playwright
import json
import os
from pathlib import Path
import getpass
import time
import sys
import shlex
import difflib
from typing import Dict, List
from datetime import datetime
import requests
from bs4 import BeautifulSoup

from colorama import init as colorama_init, Fore, Style

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.rule import Rule
from rich.prompt import Prompt, IntPrompt

def ensure_playwright_browsers():
    """Ensure Playwright browsers are installed, install if missing."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to launch chromium briefly to check if installed
            browser = p.chromium.launch(headless=True, timeout=5000)
            browser.close()
    except Exception:
        console.print("[yellow]⚠️  Playwright browsers not found. Installing chromium...[/yellow]")
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            if result.returncode == 0:
                console.print("[green]✓ Browsers installed successfully![/green]")
            else:
                console.print(f"[red]✗ Failed to install browsers: {result.stderr}[/red]")
                console.print("[yellow]You can install manually with: playwright install chromium[/yellow]")
        except subprocess.TimeoutExpired:
            console.print("[red]✗ Browser installation timed out. Please install manually.[/red]")
        except Exception as e:
            console.print(f"[red]✗ Error installing browsers: {e}[/red]")

# Dynamic data directory for all credentials
# Uses user's Documents folder if available, otherwise home directory
DATA_DIR = Path.home() / "Documents" / "merosharedata"
if not DATA_DIR.parent.exists():
    DATA_DIR = Path.home() / "merosharedata"

DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "family_members.json"
IPO_CONFIG_FILE = DATA_DIR / "ipo_config.json"
CLI_HISTORY_FILE = DATA_DIR / "nepse_cli_history.txt"

console = Console(force_terminal=True, legacy_windows=False)
CLI_PROMPT_STYLE = PTStyle.from_dict({
    # Gemini-inspired colors
    "prompt": "bold #4da6ff",           # Bright Blue prompt
    "input": "#ffffff",                 # White input text
    
    # Completion Menu Styles
    "completion-menu": "bg:#111111 noinherit",    # Very dark background
    "completion-menu.completion": "bg:#111111 #bbbbbb", # Default text grey
    "completion-menu.completion.current": "bg:#2d2d2d #ffffff bold", # Highlighted row
    
    # Custom classes for formatted completions
    "completion-command": "bold #ffffff",       # Command name white/bold
    "completion-description": "italic #ff55ff", # Description pink/magenta
    "completion-builtin": "italic #888888",     # Built-in tag grey
    
    "scrollbar.background": "bg:#111111",
    "scrollbar.button": "bg:#555555",
})

def print_progress(step, total, message, sub_message=""):
    """
    Print a progress bar with current step
    
    Args:
        step: Current step number (1-indexed)
        total: Total number of steps
        message: Main message to display
        sub_message: Optional sub-message with arrow prefix
    """
    # Calculate progress
    percentage = int((step / total) * 100)
    filled = int((step / total) * 30)  # 30 character wide bar
    bar = "█" * filled + "░" * (30 - filled)
    
    # Print progress bar
    print(f"\r[{bar}] {percentage}% ({step}/{total}) {message}", end="", flush=True)
    
    # If this is the last step or there's a sub-message, move to new line
    if sub_message:
        print(f"\n    → {sub_message}", flush=True)
    elif step == total:
        print()  # New line at the end

def load_family_members():
    """Load all family members from config file"""
    if not CONFIG_FILE.exists():
        return {"members": []}
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_family_members(config):
    """Save family members to config file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    if os.name != 'nt':
        os.chmod(CONFIG_FILE, 0o600)

def add_family_member():
    """Add a new family member with enhanced UI"""
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]➕ Add New Family Member[/bold cyan]",
        border_style="cyan",
        box=box.DOUBLE
    ))
    
    config = load_family_members()
    
    # Member Name
    console.print("\n[bold yellow]📝 Member Information[/bold yellow]")
    member_name = Prompt.ask("[cyan]Member name[/cyan] (e.g., Dad, Mom, Me, Brother)").strip()
    
    if not member_name:
        console.print("[red]✗ Member name cannot be empty![/red]")
        return
    
    # Check if member already exists
    for member in config.get('members', []):
        if member['name'].lower() == member_name.lower():
            console.print(f"\n[yellow]⚠ Member '{member_name}' already exists![/yellow]")
            update = Prompt.ask("[cyan]Update this member?[/cyan]", choices=["yes", "no"], default="no")
            if update != 'yes':
                console.print("[yellow]✗ Cancelled[/yellow]")
                return
            config['members'].remove(member)
            break
    
    # Meroshare Credentials
    console.print("\n[bold yellow]🔐 Meroshare Credentials[/bold yellow]")
    
    # Display common DPs in a nice table
    dp_table = Table(title="Common DPs", box=box.SIMPLE, show_header=True, header_style="bold magenta")
    dp_table.add_column("DP Code", style="cyan", justify="center")
    dp_table.add_column("Name", style="white")
    dp_table.add_row("139", "CREATIVE SECURITIES PRIVATE LIMITED")
    dp_table.add_row("146", "GLOBAL IME CAPITAL LIMITED")
    dp_table.add_row("175", "NMB CAPITAL LIMITED")
    dp_table.add_row("190", "SIDDHARTHA CAPITAL LIMITED")
    console.print(dp_table)
    console.print("[dim]Type 'dplist' command to see all DPs[/dim]\n")
    
    dp_value = Prompt.ask("[cyan]DP value[/cyan] (e.g., 139)").strip()
    username = Prompt.ask("[cyan]Username[/cyan]").strip()
    password = Prompt.ask("[cyan]Password[/cyan]", password=True)
    pin = Prompt.ask("[cyan]Transaction PIN[/cyan] (4 digits)", password=True)
    
    # IPO Settings
    console.print("\n[bold yellow]📊 IPO Application Settings[/bold yellow]")
    applied_kitta = Prompt.ask("[cyan]Applied Kitta[/cyan]", default="10").strip()
    crn_number = Prompt.ask("[cyan]CRN Number[/cyan]").strip()
    
    member = {
        "name": member_name,
        "dp_value": dp_value,
        "username": username,
        "password": password,
        "transaction_pin": pin,
        "applied_kitta": int(applied_kitta),
        "crn_number": crn_number
    }
    
    if 'members' not in config:
        config['members'] = []
    
    config['members'].append(member)
    save_family_members(config)
    
    # Success message
    console.print("\n")
    console.print(Panel.fit(
        f"[bold green]✓ Member '{member_name}' added successfully![/bold green]\n"
        f"[white]Total members: {len(config['members'])}[/white]",
        border_style="green",
        box=box.DOUBLE
    ))
    console.print("")

def list_family_members():
    """List all family members with enhanced UI"""
    config = load_family_members()
    members = config.get('members', [])
    
    if not members:
        console.print(Panel("[bold red]⚠ No family members found.[/bold red]\n[yellow]Use 'add' command to add members first![/yellow]", box=box.ROUNDED, border_style="red"))
        return None
    
    table = Table(
        title="[bold cyan]👥 Family Members[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold magenta",
        expand=True,
        border_style="cyan"
    )
    table.add_column("#", style="dim", width=4, justify="center")
    table.add_column("Name", style="bold white")
    table.add_column("Username", style="cyan")
    table.add_column("DP", style="magenta", justify="center")
    table.add_column("Kitta", justify="right", style="green")
    table.add_column("CRN", style="yellow")

    for idx, member in enumerate(members, 1):
        table.add_row(
            str(idx),
            f"[bold]{member['name']}[/bold]",
            member['username'],
            member['dp_value'],
            str(member['applied_kitta']),
            member['crn_number']
        )
    
    console.print("\n")
    console.print(table)
    console.print(f"\n[dim]Total: {len(members)} member(s)[/dim]")
    return members

def select_member_interactive(title="Select Family Member", show_details=True):
    """Generic interactive member selector with arrow keys"""
    config = load_family_members()
    members = config.get('members', [])
    
    if not members:
        console.print(Panel("⚠ No family members found. Add members first!", style="bold red", box=box.ROUNDED))
        return None, None
    
    # Inline interactive selection
    selected_index = 0
    
    bindings = KeyBindings()

    @bindings.add('up')
    def _(event):
        nonlocal selected_index
        selected_index = (selected_index - 1) % len(members)

    @bindings.add('down')
    def _(event):
        nonlocal selected_index
        selected_index = (selected_index + 1) % len(members)

    @bindings.add('enter')
    def _(event):
        event.app.exit(result=(members[selected_index], selected_index))

    @bindings.add('c-c')
    def _(event):
        event.app.exit(result=(None, None))

    def get_formatted_text():
        result = []
        result.append(('class:title', f'{title} (Use ↑/↓ and Enter):\n'))
        for i, member in enumerate(members):
            if i == selected_index:
                # Highlight selected item
                result.append(('class:selected', f' > {member["name"]} (DP: {member["dp_value"]})\n'))
            else:
                result.append(('class:unselected', f'   {member["name"]} (DP: {member["dp_value"]})\n'))
        return FormattedText(result)

    # Define style for the menu
    style = PTStyle.from_dict({
        'selected': 'fg:ansigreen bold',
        'unselected': '',
        'title': 'bold underline'
    })

    # Create a small application that runs inline
    app = Application(
        layout=Layout(
            Window(content=FormattedTextControl(get_formatted_text), height=len(members) + 2)
        ),
        key_bindings=bindings,
        style=style,
        full_screen=False,  # Inline mode
        mouse_support=False
    )

    try:
        selected, index = app.run()
        
        if selected and show_details:
            console.print(f"[bold green]✓ Selected:[/bold green] {selected['name']} (Kitta: {selected['applied_kitta']} | CRN: {selected['crn_number']})")
        elif not selected:
            console.print("\n[yellow]✗ Selection cancelled[/yellow]")
            
        return selected, index
    except Exception as e:
        console.print(f"[yellow]Interactive menu failed ({str(e)}). Please try again.[/yellow]")
        return None, None

def select_family_member():
    """Select a family member for IPO application using an inline interactive menu"""
    selected, _ = select_member_interactive("Select Family Member", show_details=True)
    return selected

def edit_family_member():
    """Edit an existing family member"""
    config = load_family_members()
    members = config.get('members', [])
    
    if not members:
        console.print(Panel("[bold red]⚠ No family members found.[/bold red]\n[yellow]Use 'add' command to add members first![/yellow]", box=box.ROUNDED, border_style="red"))
        return
    
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]✏️  Edit Family Member[/bold cyan]",
        border_style="cyan",
        box=box.DOUBLE
    ))
    console.print("\n")
    
    # Use interactive selection
    member, index = select_member_interactive("Select member to edit", show_details=False)
    
    if not member:
        return
    
    try:
        
        console.print("\n")
        console.print(Panel.fit(
            f"[bold cyan]✏️  Edit Member: {member['name']}[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE
        ))
        
        console.print("\n[dim]Press Enter to keep current value[/dim]\n")
        
        # Edit fields
        console.print("[bold yellow]📝 Member Information[/bold yellow]")
        new_name = Prompt.ask("[cyan]Member name[/cyan]", default=member['name']).strip()
        
        console.print("\n[bold yellow]🔐 Meroshare Credentials[/bold yellow]")
        new_dp = Prompt.ask("[cyan]DP value[/cyan]", default=member['dp_value']).strip()
        new_username = Prompt.ask("[cyan]Username[/cyan]", default=member['username']).strip()
        
        update_pwd = Prompt.ask("[cyan]Update password?[/cyan]", choices=["yes", "no"], default="no")
        if update_pwd == "yes":
            new_password = Prompt.ask("[cyan]New password[/cyan]", password=True)
        else:
            new_password = member['password']
        
        update_pin = Prompt.ask("[cyan]Update PIN?[/cyan]", choices=["yes", "no"], default="no")
        if update_pin == "yes":
            new_pin = Prompt.ask("[cyan]New PIN[/cyan] (4 digits)", password=True)
        else:
            new_pin = member['transaction_pin']
        
        console.print("\n[bold yellow]📊 IPO Application Settings[/bold yellow]")
        new_kitta = Prompt.ask("[cyan]Applied Kitta[/cyan]", default=str(member['applied_kitta'])).strip()
        new_crn = Prompt.ask("[cyan]CRN Number[/cyan]", default=member['crn_number']).strip()
        
        # Update member
        member['name'] = new_name
        member['dp_value'] = new_dp
        member['username'] = new_username
        member['password'] = new_password
        member['transaction_pin'] = new_pin
        member['applied_kitta'] = int(new_kitta)
        member['crn_number'] = new_crn
        
        save_family_members(config)
        
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]✓ Member '{new_name}' updated successfully![/bold green]",
            border_style="green",
            box=box.DOUBLE
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Edit cancelled[/yellow]")
        return

def delete_family_member():
    """Delete a family member"""
    config = load_family_members()
    members = config.get('members', [])
    
    if not members:
        console.print(Panel("[bold red]⚠ No family members found.[/bold red]\n[yellow]Use 'add' command to add members first![/yellow]", box=box.ROUNDED, border_style="red"))
        return
    
    console.print("\n")
    console.print(Panel.fit(
        "[bold red]🗑️  Delete Family Member[/bold red]",
        border_style="red",
        box=box.DOUBLE
    ))
    console.print("\n")
    
    # Use interactive selection
    member, index = select_member_interactive("Select member to delete", show_details=False)
    
    if not member:
        return
    
    try:
        
        console.print("\n")
        console.print(Panel.fit(
            f"[bold red]🗑️  Delete Member: {member['name']}[/bold red]\n\n"
            f"[yellow]⚠ This action cannot be undone![/yellow]",
            border_style="red",
            box=box.DOUBLE
        ))
        
        confirm = Prompt.ask("\n[red]Type the member name to confirm deletion[/red]").strip()
        
        if confirm.lower() != member['name'].lower():
            console.print("[yellow]✗ Deletion cancelled - name didn't match[/yellow]")
            return
        
        members.pop(index)
        config['members'] = members
        save_family_members(config)
        
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]✓ Member '{member['name']}' deleted successfully![/bold green]\n"
            f"[white]Remaining members: {len(members)}[/white]",
            border_style="green",
            box=box.DOUBLE
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Deletion cancelled[/yellow]")
        return

def manage_family_members():
    """Interactive family member management menu with arrow key navigation"""
    menu_options = [
        ("1", "➕ Add new member", add_family_member),
        ("2", "📋 List all members", lambda: (list_family_members(), input("\nPress Enter to continue..."))),
        ("3", "✏️  Edit member", edit_family_member),
        ("4", "🗑️  Delete member", delete_family_member),
        ("5", "🔙 Back to main menu", None)
    ]
    
    while True:
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]👥 Family Member Management[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE
        ))
        console.print("\n")
        
        # Interactive menu selection
        selected_index = 0
        bindings = KeyBindings()

        @bindings.add('up')
        def _(event):
            nonlocal selected_index
            selected_index = (selected_index - 1) % len(menu_options)

        @bindings.add('down')
        def _(event):
            nonlocal selected_index
            selected_index = (selected_index + 1) % len(menu_options)

        @bindings.add('enter')
        def _(event):
            event.app.exit(result=selected_index)

        @bindings.add('c-c')
        def _(event):
            event.app.exit(result=None)

        def get_formatted_text():
            result = []
            result.append(('class:title', 'Select an option (Use ↑/↓ and Enter):\n\n'))
            for i, (num, desc, _) in enumerate(menu_options):
                if i == selected_index:
                    result.append(('class:selected', f' > {desc}\n'))
                else:
                    result.append(('class:unselected', f'   {desc}\n'))
            return FormattedText(result)

        style = PTStyle.from_dict({
            'selected': 'fg:ansigreen bold',
            'unselected': '',
            'title': 'bold underline'
        })

        app = Application(
            layout=Layout(
                Window(content=FormattedTextControl(get_formatted_text), height=len(menu_options) + 3)
            ),
            key_bindings=bindings,
            style=style,
            full_screen=False,
            mouse_support=False
        )

        try:
            choice_index = app.run()
            
            if choice_index is None or choice_index == 4:  # Cancelled or Back
                break
            
            # Execute the selected function
            func = menu_options[choice_index][2]
            if func:
                func()
                
        except KeyboardInterrupt:
            console.print("\n[yellow]✗ Cancelled[/yellow]")
            break

def save_credentials():
    """Legacy function - redirects to add_family_member"""
    return add_family_member()

def load_credentials():
    """Load credentials - for backward compatibility"""
    # Check for old single-member config
    old_config_file = DATA_DIR / "meroshare_config.json"
    if old_config_file.exists() and not CONFIG_FILE.exists():
        print("\n⚠ Old config format detected. Migrating to multi-member format...\n")
        with open(old_config_file, 'r') as f:
            old_config = json.load(f)
        
        # Migrate to new format
        member_name = input("Enter name for this member (e.g., Me): ").strip() or "Me"
        
        new_config = {
            "members": [{
                "name": member_name,
                "dp_value": old_config.get('dp_value', ''),
                "username": old_config.get('username', ''),
                "password": old_config.get('password', ''),
                "transaction_pin": old_config.get('transaction_pin', ''),
                "applied_kitta": 10,
                "crn_number": ""
            }]
        }
        
        save_family_members(new_config)
        print(f"✓ Migrated to new format as '{member_name}'\n")
        
        # Backup old file
        os.rename(old_config_file, old_config_file + ".backup")
    
    config = load_family_members()
    
    if not config.get('members'):
        print("\n⚠ No family members found. Let's add one!\n")
        add_family_member()
        config = load_family_members()
    
    return config

def update_credentials():
    """Legacy function - redirects to add_family_member"""
    add_family_member()

def meroshare_login(auto_load=True, headless=False):
    """
    Automated login for Meroshare with correct selectors
    
    Args:
        auto_load: Load credentials from config file
        headless: Run browser in headless mode (no GUI)
    """
    if auto_load:
        print("Loading credentials...")
        config = load_credentials()
        dp_value = config['dp_value']
        username = config['username']
        password = config['password']
    else:
        dp_value = input("Enter DP value: ")
        username = input("Enter username: ")
        password = getpass.getpass("Enter password: ")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            print_progress(1, 6, "Navigating to Meroshare...")
            page.goto("https://meroshare.cdsc.com.np/#/login", wait_until="networkidle")
            time.sleep(2)
            
            # Select2 dropdown - click to open
            print_progress(2, 6, "Opening DP dropdown...")
            page.click("span.select2-selection")
            time.sleep(1)
            
            # Select the option - Select2 creates a results list in the DOM
            print_progress(3, 6, f"Selecting DP (value: {dp_value})...")
            # Wait for dropdown results to appear
            page.wait_for_selector(".select2-results", timeout=5000)
            
            # Type in search box and select
            search_box = page.query_selector("input.select2-search__field")
            if search_box:
                print(f"    → Searching for DP value {dp_value}...")
                search_box.type(dp_value)
                time.sleep(0.5)
                
                # Click the first result or press Enter
                first_result = page.query_selector("li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']")
                if first_result:
                    first_result.click()
                else:
                    page.keyboard.press("Enter")
            else:
                # Fallback: click by text
                try:
                    results = page.query_selector_all("li.select2-results__option")
                    for result in results:
                        if dp_value in result.inner_text():
                            result.click()
                            break
                except:
                    print("    ⚠ Using fallback selection method...")
                    page.select_option("select.select2-hidden-accessible", dp_value)
            
            time.sleep(1)
            
            # Fill username - try multiple possible selectors
            print_progress(4, 6, "Filling username...")
            username_selectors = [
                "input[formcontrolname='username']",
                "input#username",
                "input[placeholder*='User']"
            ]
            for selector in username_selectors:
                try:
                    page.fill(selector, username, timeout=2000)
                    break
                except:
                    continue
            
            # Fill password
            print_progress(5, 6, "Filling password...")
            password_selectors = [
                "input[formcontrolname='password']",
                "input[type='password']"
            ]
            for selector in password_selectors:
                try:
                    page.fill(selector, password, timeout=2000)
                    break
                except:
                    continue
            
            # Click login button
            print_progress(6, 6, "Clicking login button...")
            login_button_selectors = [
                "button.btn.sign-in",
                "button[type='submit']",
                "button:has-text('Login')"
            ]
            for selector in login_button_selectors:
                try:
                    page.click(selector, timeout=2000)
                    break
                except:
                    continue
            
            # Wait for response - try to detect navigation
            print("\nWaiting for response...")
            try:
                # Wait for navigation or some change (max 8 seconds)
                page.wait_for_load_state("networkidle", timeout=8000)
            except:
                print("    (networkidle timeout - page may still be loading)")
            
            time.sleep(2)  # extra buffer for any JS to complete
            
            # Angular apps: wait for hash route to change from #/login to #/dashboard
            print("Waiting for Angular routing...")
            try:
                # Wait up to 3 seconds for URL to change away from #/login
                page.wait_for_function("window.location.hash !== '#/login'", timeout=3000)
                time.sleep(0.5)  # small buffer for final render
            except:
                print("    (route didn't change, but may still be logged in)")
            
            # Check result - multiple detection methods
            current_url = page.url
            print(f"\nCurrent URL: {current_url}")
            
            # Method 1: Check URL patterns (Angular hash routing)
            url_success = False
            if "#/login" not in current_url.lower():
                url_success = True
                print("✓ URL changed from login page")
            
            # Method 2: Check if login form is still visible
            form_gone = False
            try:
                login_form_visible = page.is_visible("input[formcontrolname='username']", timeout=1000)
                if not login_form_visible:
                    form_gone = True
                    print("✓ Login form disappeared")
            except:
                form_gone = True
                print("✓ Login form not found")
            
            # Method 3: Look for success indicators
            success_elements = [
                "a[href*='dashboard']",
                "button:has-text('Logout')",
                ".user-info, .user-profile",
                "[class*='dashboard']"
            ]
            found_success_element = False
            for selector in success_elements:
                try:
                    if page.query_selector(selector):
                        found_success_element = True
                        print(f"✓ Found success indicator: {selector}")
                        break
                except:
                    pass
            
            # Method 4: Check for error messages
            error_found = False
            try:
                errors = page.query_selector_all(".error, .alert-danger, .text-danger, [class*='error'], .invalid-feedback")
                for error in errors:
                    text = error.inner_text().strip()
                    if text and len(text) > 0:
                        print(f"⚠ Error message found: {text}")
                        error_found = True
            except:
                pass
            
            # Final verdict
            if error_found:
                print("\n✗ LOGIN FAILED - Error message detected")
                # Take screenshot for debugging
                try:
                    screenshot_path = "login_error.png"
                    page.screenshot(path=screenshot_path)
                    print(f"📸 Screenshot saved to {screenshot_path}")
                except:
                    pass
            elif url_success or form_gone or found_success_element:
                print("\n✓✓✓ LOGIN SUCCESSFUL! ✓✓✓")
                print(f"Page URL: {current_url}")
            else:
                print("\n⚠ Login status uncertain - please verify manually")
                print(f"URL contains 'login': {'login' in current_url.lower()}")
                # Take screenshot for debugging
                try:
                    screenshot_path = "login_uncertain.png"
                    page.screenshot(path=screenshot_path)
                    print(f"📸 Screenshot saved to {screenshot_path}")
                except:
                    pass
            
            # In headless mode, don't wait
            if not headless:
                print("\nBrowser will stay open for 30 seconds...")
                time.sleep(30)
            else:
                print("\n✓ Script completed in headless mode")
                time.sleep(2)
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            if not headless:
                time.sleep(5)
            
        finally:
            browser.close()

def get_portfolio(auto_load=True, headless=False):
    """
    Login and fetch portfolio holdings from Meroshare
    
    Args:
        auto_load: Load credentials from config file
        headless: Run browser in headless mode (no GUI)
    """
    if auto_load:
        print("Loading credentials...")
        config = load_credentials()
        dp_value = config['dp_value']
        username = config['username']
        password = config['password']
    else:
        dp_value = input("Enter DP value: ")
        username = input("Enter username: ")
        password = getpass.getpass("Enter password: ")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Use the EXACT same login logic that works in meroshare_login()
            print(); print_progress(1, 7, "Navigating to Meroshare...")
            page.goto("https://meroshare.cdsc.com.np/#/login", wait_until="networkidle")
            time.sleep(2)
            
            # Select2 dropdown - click to open
            print_progress(2, 7, "Opening DP dropdown...")
            page.click("span.select2-selection")
            time.sleep(1)
            
            # Select the option - Select2 creates a results list in the DOM
            print_progress(3, 7, f"Selecting DP (value: {dp_value})...")
            # Wait for dropdown results to appear
            page.wait_for_selector(".select2-results", timeout=5000)
            
            # Type in search box and select
            search_box = page.query_selector("input.select2-search__field")
            if search_box:
                print(f"    → Searching for DP value {dp_value}...")
                search_box.type(dp_value)
                time.sleep(0.5)
                
                # Click the first result or press Enter
                first_result = page.query_selector("li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']")
                if first_result:
                    first_result.click()
                else:
                    page.keyboard.press("Enter")
            else:
                # Fallback: click by text
                try:
                    results = page.query_selector_all("li.select2-results__option")
                    for result in results:
                        if dp_value in result.inner_text():
                            result.click()
                            break
                except:
                    print("    ⚠ Using fallback selection method...")
                    page.select_option("select.select2-hidden-accessible", dp_value)
            
            time.sleep(1)
            
            # Fill username - try multiple possible selectors
            print_progress(4, 7, "Filling username...")
            username_selectors = [
                "input[formcontrolname='username']",
                "input#username",
                "input[placeholder*='User']"
            ]
            for selector in username_selectors:
                try:
                    page.fill(selector, username, timeout=2000)
                    break
                except:
                    continue
            
            # Fill password
            print_progress(5, 7, "Filling password...")
            password_selectors = [
                "input[formcontrolname='password']",
                "input[type='password']"
            ]
            for selector in password_selectors:
                try:
                    page.fill(selector, password, timeout=2000)
                    break
                except:
                    continue
            
            # Click login button
            print_progress(6, 7, "Clicking login button...")
            login_button_selectors = [
                "button.btn.sign-in",
                "button[type='submit']",
                "button:has-text('Login')"
            ]
            for selector in login_button_selectors:
                try:
                    page.click(selector, timeout=2000)
                    break
                except:
                    continue
            
            # Wait for login to complete - same as working login function
            print(); print_progress(7, 7, "Waiting for login...")
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except:
                print("    (networkidle timeout - page may still be loading)")
            
            time.sleep(2)
            
            # Wait for Angular routing
            print("Waiting for Angular routing...")
            try:
                page.wait_for_function("window.location.hash !== '#/login'", timeout=3000)
                time.sleep(0.5)
            except:
                print("    (route didn't change, but may still be logged in)")
            
            # Check if logged in
            current_url = page.url
            print(f"Current URL: {current_url}")
            
            if "#/login" not in current_url.lower() or page.query_selector("a[href*='dashboard']"):
                print("✓ Login successful!")
            else:
                print("⚠ Login may have failed, but continuing to portfolio...")
            
            # Navigate to Portfolio
            print("\n📊 Navigating to Portfolio page...")
            page.goto("https://meroshare.cdsc.com.np/#/portfolio", wait_until="networkidle")
            time.sleep(3)
            
            print("Fetching holdings...\n")
            
            # Extract portfolio data with correct selectors
            try:
                # Wait for the table to load (Angular app with _ngcontent attributes)
                print("Waiting for portfolio table to load...")
                page.wait_for_selector("table.table tbody tr", timeout=10000)
                time.sleep(2)
                
                # Get all data rows (excluding the total row)
                rows = page.query_selector_all("table.table tbody:first-of-type tr")
                
                if rows and len(rows) > 0:
                    table = Table(title="YOUR PORTFOLIO HOLDINGS", box=box.ROUNDED, header_style="bold cyan", expand=True)
                    table.add_column("#", style="dim", width=4)
                    table.add_column("Scrip", style="bold white")
                    table.add_column("Balance", justify="right")
                    table.add_column("Last Price", justify="right")
                    table.add_column("Value (Last)", justify="right")
                    table.add_column("LTP", justify="right")
                    table.add_column("Value (LTP)", justify="right", style="green")
                    
                    portfolio_data = []
                    total_value_last = 0
                    total_value_ltp = 0
                    
                    for row in rows:
                        cells = row.query_selector_all("td")
                        if cells and len(cells) >= 7:
                            # Extract each column
                            num = cells[0].inner_text().strip()
                            scrip = cells[1].inner_text().strip()
                            balance = cells[2].inner_text().strip()
                            last_price = cells[3].inner_text().strip()
                            value_last = cells[4].inner_text().strip()
                            ltp = cells[5].inner_text().strip()
                            value_ltp = cells[6].inner_text().strip()
                            
                            # Store as structured data
                            holding = {
                                "number": num,
                                "scrip": scrip,
                                "current_balance": balance,
                                "last_closing_price": last_price,
                                "value_as_of_last_price": value_last,
                                "last_transaction_price": ltp,
                                "value_as_of_ltp": value_ltp
                            }
                            portfolio_data.append(holding)
                            
                            table.add_row(num, scrip, balance, last_price, value_last, ltp, value_ltp)
                    
                    # Get total row (from second tbody)
                    total_rows = page.query_selector_all("table.table tbody:last-of-type tr")
                    if total_rows and len(total_rows) > 0:
                        total_cells = total_rows[0].query_selector_all("td")
                        if total_cells and len(total_cells) >= 5:
                            total_last = total_cells[4].inner_text().strip()
                            total_ltp = total_cells[6].inner_text().strip() if len(total_cells) > 6 else ""
                            
                            table.add_section()
                            table.add_row("TOTAL", "", "", "", total_last, "", total_ltp, style="bold")
                    
                    console.print(table)
                    console.print(f"✓ Total holdings: {len(portfolio_data)} scrips\n")
                    
                    # Save to JSON with metadata
                    output_file = "portfolio_data.json"
                    output = {
                        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_scrips": len(portfolio_data),
                        "holdings": portfolio_data
                    }
                    with open(output_file, 'w') as f:
                        json.dump(output, f, indent=2)
                    print(f"✓ Portfolio data saved to {output_file}")
                    
                else:
                    console.print(Panel("⚠ No portfolio data found.", style="bold yellow", box=box.ROUNDED))
            except Exception as e:
                print(f"⚠ Error extracting portfolio: {e}")
                screenshot_path = "portfolio_error.png"
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"📸 Screenshot saved to {screenshot_path}")
            
            # Keep browser open in non-headless mode
            if not headless:
                print("\nBrowser will stay open for 30 seconds...")
                time.sleep(30)
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            if not headless:
                time.sleep(5)
        finally:
            browser.close()

def load_ipo_config():
    """Load IPO application configuration"""
    if not IPO_CONFIG_FILE.exists():
        print(f"\n⚠ IPO config file not found. Creating template...")
        default_config = {
            "applied_kitta": 10,
            "crn_number": "YOUR_CRN_NUMBER_HERE"
        }
        with open(IPO_CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"✓ Created {IPO_CONFIG_FILE}")
        print(f"⚠ Please edit {IPO_CONFIG_FILE} with your actual CRN number before applying!\n")
        return default_config
    
    with open(IPO_CONFIG_FILE, 'r') as f:
        return json.load(f)

def apply_ipo(auto_load=True, headless=False):
    """
    Complete IPO application automation with family member selection
    
    Args:
        auto_load: Load credentials from config file
        headless: Run browser in headless mode (no GUI)
    """
    if auto_load:
        # Select family member
        member = select_family_member()
        if not member:
            print("\n✗ No member selected. Exiting...")
            return
        
        dp_value = member['dp_value']
        username = member['username']
        password = member['password']
        transaction_pin = member['transaction_pin']
        applied_kitta = member['applied_kitta']
        crn_number = member['crn_number']
        member_name = member['name']
    else:
        member_name = "Manual Entry"
        dp_value = input("Enter DP value: ")
        username = input("Enter username: ")
        password = getpass.getpass("Enter password: ")
        transaction_pin = getpass.getpass("Enter 4-digit transaction PIN: ")
        applied_kitta = int(input("Applied Kitta: ").strip() or "10")
        crn_number = input("CRN Number: ").strip()
    
    if not crn_number:
        print(f"\n✗ CRN number is required!")
        return
    
    print(f"\n✓ Applying IPO for: {member_name}")
    print(f"✓ Kitta: {applied_kitta} | CRN: {crn_number}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # ========== PHASE 1: LOGIN ==========
            print("\n" + "="*60)
            print("PHASE 1: LOGIN")
            print("="*60)
            
            print(); print_progress(1, 6, "Navigating to Meroshare...")
            page.goto("https://meroshare.cdsc.com.np/#/login", wait_until="networkidle")
            time.sleep(2)
            
            print_progress(2, 6, "Opening DP dropdown...")
            page.click("span.select2-selection")
            time.sleep(1)
            
            print_progress(3, 6, f"Selecting DP (value: {dp_value})...")
            page.wait_for_selector(".select2-results", timeout=5000)
            
            search_box = page.query_selector("input.select2-search__field")
            if search_box:
                print(f"    → Searching for DP value {dp_value}...")
                search_box.type(dp_value)
                time.sleep(0.5)
                
                # Click the first result or press Enter
                first_result = page.query_selector("li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']")
                if first_result:
                    first_result.click()
                else:
                    page.keyboard.press("Enter")
            else:
                # Fallback: click by text
                try:
                    results = page.query_selector_all("li.select2-results__option")
                    for result in results:
                        if dp_value in result.inner_text():
                            result.click()
                            break
                except:
                    print("    ⚠ Using fallback selection method...")
                    page.select_option("select.select2-hidden-accessible", dp_value)
            
            time.sleep(1)
            
            print_progress(4, 6, "Filling username...")
            username_selectors = [
                "input[formcontrolname='username']",
                "input#username",
                "input[placeholder*='User']"
            ]
            for selector in username_selectors:
                try:
                    page.fill(selector, username, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(5, 6, "Filling password...")
            password_selectors = [
                "input[formcontrolname='password']",
                "input[type='password']"
            ]
            for selector in password_selectors:
                try:
                    page.fill(selector, password, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(6, 6, "Clicking login button...")
            login_button_selectors = [
                "button.btn.sign-in",
                "button[type='submit']",
                "button:has-text('Login')"
            ]
            for selector in login_button_selectors:
                try:
                    page.click(selector, timeout=2000)
                    break
                except:
                    continue
            
            print("\nWaiting for login...")
            try:
                page.wait_for_function("window.location.hash !== '#/login'", timeout=8000)
                time.sleep(2)
            except:
                print("    (timeout, but may still be logged in)")
            
            if "#/login" not in page.url.lower():
                print("✓ Login successful!")
            else:
                print("⚠ Login may have failed, but continuing to portfolio...")
            
            # Navigate to Portfolio
            print("\n📊 Navigating to Portfolio page...")
            page.goto("https://meroshare.cdsc.com.np/#/portfolio", wait_until="networkidle")
            time.sleep(3)
            
            print("Fetching holdings...\n")
            
            # Extract portfolio data with correct selectors
            try:
                # Wait for the table to load (Angular app with _ngcontent attributes)
                print("Waiting for portfolio table to load...")
                page.wait_for_selector("table.table tbody tr", timeout=10000)
                time.sleep(2)
                
                # Get all data rows (excluding the total row)
                rows = page.query_selector_all("table.table tbody:first-of-type tr")
                
                if rows and len(rows) > 0:
                    table = Table(title="YOUR PORTFOLIO HOLDINGS", box=box.ROUNDED, header_style="bold cyan", expand=True)
                    table.add_column("#", style="dim", width=4)
                    table.add_column("Scrip", style="bold white")
                    table.add_column("Balance", justify="right")
                    table.add_column("Last Price", justify="right")
                    table.add_column("Value (Last)", justify="right")
                    table.add_column("LTP", justify="right")
                    table.add_column("Value (LTP)", justify="right", style="green")
                    
                    portfolio_data = []
                    total_value_last = 0
                    total_value_ltp = 0
                    
                    for row in rows:
                        cells = row.query_selector_all("td")
                        if cells and len(cells) >= 7:
                            # Extract each column
                            num = cells[0].inner_text().strip()
                            scrip = cells[1].inner_text().strip()
                            balance = cells[2].inner_text().strip()
                            last_price = cells[3].inner_text().strip()
                            value_last = cells[4].inner_text().strip()
                            ltp = cells[5].inner_text().strip()
                            value_ltp = cells[6].inner_text().strip()
                            
                            # Store as structured data
                            holding = {
                                "number": num,
                                "scrip": scrip,
                                "current_balance": balance,
                                "last_closing_price": last_price,
                                "value_as_of_last_price": value_last,
                                "last_transaction_price": ltp,
                                "value_as_of_ltp": value_ltp
                            }
                            portfolio_data.append(holding)
                            
                            table.add_row(num, scrip, balance, last_price, value_last, ltp, value_ltp)
                    
                    # Get total row (from second tbody)
                    total_rows = page.query_selector_all("table.table tbody:last-of-type tr")
                    if total_rows and len(total_rows) > 0:
                        total_cells = total_rows[0].query_selector_all("td")
                        if total_cells and len(total_cells) >= 5:
                            total_last = total_cells[4].inner_text().strip()
                            total_ltp = total_cells[6].inner_text().strip() if len(total_cells) > 6 else ""
                            
                            table.add_section()
                            table.add_row("TOTAL", "", "", "", total_last, "", total_ltp, style="bold")
                    
                    console.print(table)
                    console.print(f"✓ Total holdings: {len(portfolio_data)} scrips\n")
                    
                    # Save to JSON with metadata
                    output_file = "portfolio_data.json"
                    output = {
                        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_scrips": len(portfolio_data),
                        "holdings": portfolio_data
                    }
                    with open(output_file, 'w') as f:
                        json.dump(output, f, indent=2)
                    print(f"✓ Portfolio data saved to {output_file}")
                    
                else:
                    console.print(Panel("⚠ No portfolio data found.", style="bold yellow", box=box.ROUNDED))
            except Exception as e:
                print(f"⚠ Error extracting portfolio: {e}")
                screenshot_path = "portfolio_error.png"
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"📸 Screenshot saved to {screenshot_path}")
            
            # Keep browser open in non-headless mode
            if not headless:
                print("\nBrowser will stay open for 30 seconds...")
                time.sleep(30)
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            if not headless:
                time.sleep(5)
        finally:
            browser.close()

def load_ipo_config():
    """Load IPO application configuration"""
    if not IPO_CONFIG_FILE.exists():
        print(f"\n⚠ IPO config file not found. Creating template...")
        default_config = {
            "applied_kitta": 10,
            "crn_number": "YOUR_CRN_NUMBER_HERE"
        }
        with open(IPO_CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"✓ Created {IPO_CONFIG_FILE}")
        print(f"⚠ Please edit {IPO_CONFIG_FILE} with your actual CRN number before applying!\n")
        return default_config
    
    with open(IPO_CONFIG_FILE, 'r') as f:
        return json.load(f)

def apply_ipo(auto_load=True, headless=False):
    """
    Complete IPO application automation with family member selection
    
    Args:
        auto_load: Load credentials from config file
        headless: Run browser in headless mode (no GUI)
    """
    if auto_load:
        # Select family member
        member = select_family_member()
        if not member:
            print("\n✗ No member selected. Exiting...")
            return
        
        dp_value = member['dp_value']
        username = member['username']
        password = member['password']
        transaction_pin = member['transaction_pin']
        applied_kitta = member['applied_kitta']
        crn_number = member['crn_number']
        member_name = member['name']
    else:
        member_name = "Manual Entry"
        dp_value = input("Enter DP value: ")
        username = input("Enter username: ")
        password = getpass.getpass("Enter password: ")
        transaction_pin = getpass.getpass("Enter 4-digit transaction PIN: ")
        applied_kitta = int(input("Applied Kitta: ").strip() or "10")
        crn_number = input("CRN Number: ").strip()
    
    if not crn_number:
        print(f"\n✗ CRN number is required!")
        return
    
    print(f"\n✓ Applying IPO for: {member_name}")
    print(f"✓ Kitta: {applied_kitta} | CRN: {crn_number}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # ========== PHASE 1: LOGIN ==========
            print("\n" + "="*60)
            print("PHASE 1: LOGIN")
            print("="*60)
            
            print(); print_progress(1, 6, "Navigating to Meroshare...")
            page.goto("https://meroshare.cdsc.com.np/#/login", wait_until="networkidle")
            time.sleep(2)
            
            print_progress(2, 6, "Opening DP dropdown...")
            page.click("span.select2-selection")
            time.sleep(1)
            
            print_progress(3, 6, f"Selecting DP (value: {dp_value})...")
            page.wait_for_selector(".select2-results", timeout=5000)
            
            search_box = page.query_selector("input.select2-search__field")
            if search_box:
                print(f"    → Searching for DP value {dp_value}...")
                search_box.type(dp_value)
                time.sleep(0.5)
                
                # Click the first result or press Enter
                first_result = page.query_selector("li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']")
                if first_result:
                    first_result.click()
                else:
                    page.keyboard.press("Enter")
            else:
                # Fallback: click by text
                try:
                    results = page.query_selector_all("li.select2-results__option")
                    for result in results:
                        if dp_value in result.inner_text():
                            result.click()
                            break
                except:
                    print("    ⚠ Using fallback selection method...")
                    page.select_option("select.select2-hidden-accessible", dp_value)
            
            time.sleep(1)
            
            print_progress(4, 6, "Filling username...")
            username_selectors = [
                "input[formcontrolname='username']",
                "input#username",
                "input[placeholder*='User']"
            ]
            for selector in username_selectors:
                try:
                    page.fill(selector, username, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(5, 6, "Filling password...")
            password_selectors = [
                "input[formcontrolname='password']",
                "input[type='password']"
            ]
            for selector in password_selectors:
                try:
                    page.fill(selector, password, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(6, 6, "Clicking login button...")
            login_button_selectors = [
                "button.btn.sign-in",
                "button[type='submit']",
                "button:has-text('Login')"
            ]
            for selector in login_button_selectors:
                try:
                    page.click(selector, timeout=2000)
                    break
                except:
                    continue
            
            print("\nWaiting for login...")
            try:
                page.wait_for_function("window.location.hash !== '#/login'", timeout=8000)
                time.sleep(2)
            except:
                print("    (timeout, but may still be logged in)")
            
            # ========== PHASE 2: FETCH AVAILABLE IPOs ==========
            print("\n" + "="*60)
            print("PHASE 2: FETCH AVAILABLE IPOs")
            print("="*60)
            
            print("\nNavigating to ASBA page...")
            page.goto("https://meroshare.cdsc.com.np/#/asba", wait_until="networkidle")
            time.sleep(3)
            
            print("Fetching IPO list...\n")
            
            try:
                page.wait_for_selector(".company-list", timeout=10000)
                time.sleep(2)
            except Exception as e:
                print("⚠ No IPOs currently available on Meroshare")
                print("✗ Cannot proceed with IPO application\n")
                
                try:
                    no_data = page.query_selector("text=No Data Available")
                    if no_data:
                        print("→ Meroshare shows: 'No Data Available'")
                except:
                    pass
                
                page.screenshot(path="no_ipos_available.png")
                print("📸 Screenshot saved: no_ipos_available.png\n")
                
                if not headless:
                    print("Browser will stay open for 20 seconds...")
                    time.sleep(20)
                
                return
            
            company_rows = page.query_selector_all(".company-list")
            
            available_ipos = []
            for idx, row in enumerate(company_rows, 1):
                try:
                    company_name_elem = row.query_selector(".company-name span")
                    share_type_elem = row.query_selector(".share-of-type")
                    share_group_elem = row.query_selector(".isin")
                    
                    if company_name_elem and share_type_elem and share_group_elem:
                        company_name = company_name_elem.inner_text().strip()
                        share_type = share_type_elem.inner_text().strip()
                        share_group = share_group_elem.inner_text().strip()
                        
                        if "ipo" in share_type.lower() and "ordinary" in share_group.lower():
                            # Check for both Apply and Edit buttons
                            apply_button = row.query_selector("button.btn-issue")
                            
                            # Check if IPO is already applied (button shows 'Edit')
                            is_applied = False
                            button_text = ""
                            if apply_button:
                                button_text = apply_button.inner_text().strip().lower()
                                is_applied = "edit" in button_text or "view" in button_text
                            
                            if apply_button:
                                available_ipos.append({
                                    "index": len(available_ipos) + 1,
                                    "company_name": company_name,
                                    "share_type": share_type,
                                    "share_group": share_group,
                                    "element": row,
                                    "apply_button": apply_button,
                                    "is_applied": is_applied,
                                    "button_text": button_text
                                })
                except Exception as e:
                    print(f"    Error parsing row {idx}: {e}")
            
            if not available_ipos:
                print("✗ No IPOs (Ordinary Shares) available to apply!")
                page.screenshot(path="no_ipos_found.png")
                return
            
            print("="*60)
            print("AVAILABLE IPOs (Ordinary Shares)")
            print("="*60)
            for ipo in available_ipos:
                print(f"{ipo['index']}. {ipo['company_name']}")
                print(f"   Type: {ipo['share_type']} | Group: {ipo['share_group']}")
                print()
            print("="*60)
            
            if not headless:
                selection = input(f"\nEnter IPO number to apply (1-{len(available_ipos)}): ").strip()
                try:
                    selected_idx = int(selection) - 1
                    if selected_idx < 0 or selected_idx >= len(available_ipos):
                        print("✗ Invalid selection!")
                        return
                except ValueError:
                    print("✗ Invalid input!")
                    return
            else:
                selected_idx = 0
                print(f"\n→ Auto-selecting IPO #1: {available_ipos[0]['company_name']}")
            
            selected_ipo = available_ipos[selected_idx]
            print(f"\n✓ Selected: {selected_ipo['company_name']}\n")
            
            # Check if IPO is already applied
            if selected_ipo.get('is_applied', False):
                print(f"⚠ IPO already applied for this account!")
                print(f"   Button shows: '{selected_ipo.get('button_text', 'N/A').title()}'")
                print(f"   (Edit button indicates IPO was already applied)")
                page.screenshot(path="ipo_already_applied.png")
                print("📸 Screenshot saved: ipo_already_applied.png\n")
                
                if not headless:
                    print("Browser will stay open for 20 seconds...")
                    time.sleep(20)
                return
            
            print("Clicking Apply button...")
            selected_ipo['apply_button'].click()
            time.sleep(3)
            
            page.screenshot(path="ipo_form_loaded.png")
            print("✓ IPO form loaded")
            
            # ========== PHASE 3: FILL IPO APPLICATION FORM ==========
            print("\n" + "="*60)
            print("PHASE 3: FILL APPLICATION FORM")
            print("="*60)
            
            page.wait_for_selector("select#selectBank", timeout=10000)
            time.sleep(2)
            
            print(); print_progress(1, 5, "Selecting bank...")
            bank_options = page.query_selector_all("select#selectBank option")
            valid_banks = [opt for opt in bank_options if opt.get_attribute("value")]
            
            if len(valid_banks) == 1:
                bank_value = valid_banks[0].get_attribute("value")
                bank_name = valid_banks[0].inner_text().strip()
                print(f"    → Auto-selected: {bank_name}")
                page.select_option("select#selectBank", bank_value)
            elif len(valid_banks) > 1:
                print(f"    → Found {len(valid_banks)} banks, selecting first one")
                bank_value = valid_banks[0].get_attribute("value")
                page.select_option("select#selectBank", bank_value)
            else:
                print("    ✗ No banks found!")
                return
            
            time.sleep(2)
            
            print(); print_progress(2, 5, "Selecting account number...")
            page.wait_for_selector("select#accountNumber", timeout=5000)
            account_options = page.query_selector_all("select#accountNumber option")
            valid_accounts = [opt for opt in account_options if opt.get_attribute("value")]
            
            if len(valid_accounts) == 1:
                account_value = valid_accounts[0].get_attribute("value")
                account_text = valid_accounts[0].inner_text().strip()
                print(f"    → Auto-selected: {account_text}")
                page.select_option("select#accountNumber", account_value)
            elif len(valid_accounts) > 1:
                print(f"    → Found {len(valid_accounts)} accounts, selecting first one")
                account_value = valid_accounts[0].get_attribute("value")
                page.select_option("select#accountNumber", account_value)
            else:
                print("    ✗ No accounts found!")
                return
            
            time.sleep(2)
            
            print(); print_progress(3, 5, "Waiting for branch to auto-fill...")
            time.sleep(1)
            branch_value = page.input_value("input#selectBranch")
            if branch_value:
                print(f"    → Branch: {branch_value}")
            
            print(); print_progress(4, 5, f"Filling applied kitta: {applied_kitta}")
            page.fill("input#appliedKitta", str(applied_kitta))
            time.sleep(1)
            
            amount_value = page.input_value("input#amount")
            print(f"    → Amount: {amount_value}")
            
            print(); print_progress(5, 5, f"Filling CRN: {crn_number}")
            page.fill("input#crnNumber", crn_number)
            time.sleep(1)
            
            page.screenshot(path="form_filled.png")
            print("\n✓ Form filled successfully")
            
            # ========== PHASE 4: ACCEPT DISCLAIMER & PROCEED ==========
            print("\n" + "="*60)
            print("PHASE 4: ACCEPT DISCLAIMER & PROCEED")
            print("="*60)
            
            print("\nChecking disclaimer checkbox...")
            disclaimer_checkbox = page.query_selector("input#disclaimer")
            if disclaimer_checkbox:
                disclaimer_checkbox.check()
                print("✓ Disclaimer accepted")
            else:
                print("⚠ Disclaimer checkbox not found")
            
            time.sleep(1)
            
            print("\nClicking Proceed button...")
            proceed_button = page.query_selector("button.btn-primary[type='submit']")
            if proceed_button:
                proceed_button.click()
                print("✓ Clicked Proceed")
            else:
                print("✗ Proceed button not found!")
                page.screenshot(path="proceed_error.png")
                return
            
            time.sleep(3)
            
            # ========== PHASE 5: ENTER TRANSACTION PIN ==========
            print("\n" + "="*60)
            print("PHASE 5: ENTER TRANSACTION PIN")
            print("="*60)
            
            print("\nWaiting for PIN entry screen...")
            page.wait_for_selector("input#transactionPIN", timeout=10000)
            time.sleep(2)
            
            page.screenshot(path="pin_screen.png")
            print("✓ PIN entry screen loaded")
            
            print(f"\nEntering transaction PIN...")
            page.fill("input#transactionPIN", transaction_pin)
            print("✓ PIN entered")
            
            time.sleep(1)
            
            # ========== PHASE 6: FINAL SUBMISSION ==========
            print("\n" + "="*60)
            print("PHASE 6: FINAL SUBMISSION")
            print("="*60)
            
            if not headless:
                confirm = input("\n⚠ Ready to submit application? (yes/no): ").strip().lower()
                if confirm != 'yes':
                    print("✗ Application cancelled by user")
                    return
            
            print("\nSubmitting application...")
            
            # Wait a bit more for the button to be fully ready
            time.sleep(2)
            
            # Try multiple methods to click the Apply button
            clicked = False
            
            # Method 1: Find button with text "Apply" (more reliable)
            try:
                apply_buttons = page.query_selector_all("button:has-text('Apply')")
                for btn in apply_buttons:
                    if btn.is_visible() and not btn.is_disabled():
                        btn.click()
                        print("✓ Submit button clicked (Method 1)")
                        clicked = True
                        break
            except Exception as e:
                print(f"    Method 1 failed: {e}")
            
            # Method 2: Find by class and type in the confirm page
            if not clicked:
                try:
                    submit_button = page.query_selector("div.confirm-page-btn button.btn-primary[type='submit']")
                    if submit_button and submit_button.is_visible():
                        submit_button.click()
                        print("✓ Submit button clicked (Method 2)")
                        clicked = True
                except Exception as e:
                    print(f"    Method 2 failed: {e}")
            
            # Method 3: Find any submit button in the confirmation section
            if not clicked:
                try:
                    submit_button = page.query_selector("button.btn-gap.btn-primary[type='submit']")
                    if submit_button and submit_button.is_visible():
                        submit_button.click()
                        print("✓ Submit button clicked (Method 3)")
                        clicked = True
                except Exception as e:
                    print(f"    Method 3 failed: {e}")
            
            # Method 4: Force click using JavaScript
            if not clicked:
                try:
                    page.evaluate("""
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            if (btn.textContent.includes('Apply') && btn.type === 'submit') {
                                btn.click();
                                break;
                            }
                        }
                    """)
                    print("✓ Submit button clicked (Method 4 - JavaScript)")
                    clicked = True
                except Exception as e:
                    print(f"    Method 4 failed: {e}")
            
            if not clicked:
                print("✗ Failed to click submit button!")
                page.screenshot(path="submit_error.png")
                print("📸 Screenshot saved: submit_error.png")
                print("\nPlease click the Apply button manually.")
                if not headless:
                    time.sleep(30)
                return
            
            time.sleep(5)
            
            page.screenshot(path="submission_result.png")
            print("\n✓✓✓ APPLICATION SUBMITTED! ✓✓✓")
            print(f"📸 Screenshots saved for verification")
            print(f"Current URL: {page.url}")
            
            if not headless:
                print("\nBrowser will stay open for 30 seconds...")
                time.sleep(30)
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            page.screenshot(path="error.png")
            if not headless:
                time.sleep(10)
        finally:
            browser.close()

def get_portfolio_for_member(member, headless=False):
    """Get portfolio for a specific family member"""
    print(f"\nFetching portfolio for: {member['name']}...")
    
    # Call existing get_portfolio but with member's credentials passed directly
    # We'll modify it to accept parameters
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            dp_value = member['dp_value']
            username = member['username']
            password = member['password']
            
            print(); print_progress(1, 7, "Navigating to Meroshare...")
            page.goto("https://meroshare.cdsc.com.np/#/login", wait_until="networkidle")
            time.sleep(2)
            
            print_progress(2, 7, "Opening DP dropdown...")
            page.click("span.select2-selection")
            time.sleep(1)
            
            print_progress(3, 7, f"Selecting DP...")
            page.wait_for_selector(".select2-results", timeout=5000)
            search_box = page.query_selector("input.select2-search__field")
            if search_box:
                search_box.type(dp_value)
                time.sleep(0.5)
                first_result = page.query_selector("li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']")
                if first_result:
                    first_result.click()
                else:
                    page.keyboard.press("Enter")
            time.sleep(1)
            
            print_progress(4, 7, "Filling username...")
            username_selectors = [
                "input[formcontrolname='username']",
                "input#username",
                "input[placeholder*='User']"
            ]
            for selector in username_selectors:
                try:
                    page.fill(selector, username, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(5, 7, "Filling password...")
            password_selectors = [
                "input[formcontrolname='password']",
                "input[type='password']"
            ]
            for selector in password_selectors:
                try:
                    page.fill(selector, password, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(6, 7, "Clicking login...")
            login_button_selectors = [
                "button.btn.sign-in",
                "button[type='submit']",
                "button:has-text('Login')"
            ]
            for selector in login_button_selectors:
                try:
                    page.click(selector, timeout=2000)
                    break
                except:
                    continue
            
            print(); print_progress(7, 7, "Waiting for login...")
            page.wait_for_load_state("networkidle", timeout=8000)
            time.sleep(2)
            
            print(f"✓ Logged in as {member['name']}")
            
            # Navigate to portfolio
            print("\n📊 Navigating to Portfolio...")
            page.goto("https://meroshare.cdsc.com.np/#/portfolio", wait_until="networkidle")
            time.sleep(3)
            
            print("Fetching holdings...\n")
            page.wait_for_selector("table.table tbody tr", timeout=10000)
            time.sleep(2)
            
            rows = page.query_selector_all("table.table tbody:first-of-type tr")
            
            if rows and len(rows) > 0:
                table = Table(title=f"PORTFOLIO: {member['name'].upper()}", box=box.ROUNDED, header_style="bold cyan", expand=True)
                table.add_column("#", style="dim", width=4)
                table.add_column("Scrip", style="bold white")
                table.add_column("Balance", justify="right")
                table.add_column("Last Price", justify="right")
                table.add_column("Value (Last)", justify="right")
                table.add_column("LTP", justify="right")
                table.add_column("Value (LTP)", justify="right", style="green")
                
                total_value_ltp = 0.0
                
                for row in rows:
                    cells = row.query_selector_all("td")
                    if cells and len(cells) >= 7:
                        num = cells[0].inner_text().strip()
                        scrip = cells[1].inner_text().strip()
                        balance = cells[2].inner_text().strip()
                        last_price = cells[3].inner_text().strip()
                        value_last = cells[4].inner_text().strip()
                        ltp = cells[5].inner_text().strip()
                        value_ltp = cells[6].inner_text().strip()
                        
                        # Calculate total
                        try:
                            value_ltp_num = float(value_ltp.replace(',', ''))
                            total_value_ltp += value_ltp_num
                        except:
                            pass
                        
                        table.add_row(num, scrip, balance, last_price, value_last, ltp, value_ltp)
                
                table.add_section()
                table.add_row("TOTAL", "", "", "", "", "", f"Rs. {total_value_ltp:,.2f}", style="bold")
                
                console.print(table)
            
            if not headless:
                print("\nBrowser will stay open for 20 seconds...")
                time.sleep(20)
                
        except Exception as e:
            print(f"\n✗ Error: {e}")
        finally:
            browser.close()

def test_login_for_member(member, headless=True):
    """Test login for a specific family member"""
    print(f"\nTesting login for: {member['name']}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            dp_value = member['dp_value']
            username = member['username']
            password = member['password']
            
            print(); print_progress(1, 7, "Navigating to Meroshare...")
            page.goto("https://meroshare.cdsc.com.np/#/login", wait_until="networkidle")
            time.sleep(2)
            
            print_progress(2, 7, "Opening DP dropdown...")
            page.click("span.select2-selection")
            time.sleep(1)
            
            print_progress(3, 7, f"Selecting DP (value: {dp_value})...")
            page.wait_for_selector(".select2-results", timeout=5000)
            
            search_box = page.query_selector("input.select2-search__field")
            if search_box:
                print(f"    → Searching for DP value {dp_value}...")
                search_box.type(dp_value)
                time.sleep(0.5)
                
                first_result = page.query_selector("li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']")
                if first_result:
                    first_result.click()
                else:
                    page.keyboard.press("Enter")
            else:
                # Fallback: click by text
                try:
                    results = page.query_selector_all("li.select2-results__option")
                    for result in results:
                        if dp_value in result.inner_text():
                            result.click()
                            break
                except:
                    print("    ⚠ Using fallback selection method...")
                    page.select_option("select.select2-hidden-accessible", dp_value)
            
            time.sleep(1)
            
            print_progress(4, 7, "Filling username...")
            username_selectors = [
                "input[formcontrolname='username']",
                "input#username",
                "input[placeholder*='User']"
            ]
            for selector in username_selectors:
                try:
                    page.fill(selector, username, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(5, 7, "Filling password...")
            password_selectors = [
                "input[formcontrolname='password']",
                "input[type='password']"
            ]
            for selector in password_selectors:
                try:
                    page.fill(selector, password, timeout=2000)
                    break
                except:
                    continue
            
            print_progress(6, 7, "Clicking login button...")
            login_button_selectors = [
                "button.btn.sign-in",
                "button[type='submit']",
                "button:has-text('Login')"
            ]
            for selector in login_button_selectors:
                try:
                    page.click(selector, timeout=2000)
                    break
                except:
                    continue
            
            print(); print_progress(7, 7, "Waiting for login...")
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except:
                print("    (networkidle timeout - page may still be loading)")
            
            time.sleep(2)
            
            try:
                page.wait_for_function("window.location.hash !== '#/login'", timeout=3000)
                time.sleep(0.5)
            except:
                print("    (route didn't change, but may still be logged in)")
            
            current_url = page.url
            print(f"\nCurrent URL: {current_url}")
            
            if "#/login" not in current_url.lower():
                print(f"\n✓✓✓ LOGIN SUCCESSFUL for {member['name']}! ✓✓✓")
            else:
                print(f"\n⚠ Login may have failed for {member['name']}")
                page.screenshot(path=f"login_test_{member['name']}.png")
            
            if not headless:
                print("\nBrowser will stay open for 20 seconds...")
                time.sleep(20)
                
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

def apply_ipo_for_all_members(headless=True):
    """Apply IPO for all family members - Sequential Login + Sequential Application"""
    
    # Load family members
    config = load_family_members()
    members = config.get('members', [])
    
    if not members:
        console.print(Panel("[bold red]⚠ No family members found. Add members first![/bold red]", box=box.ROUNDED, border_style="red"))
        return
    
    # Display members FIRST
    table = Table(title="Family Members to Apply IPO", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("No.", justify="right", style="cyan")
    table.add_column("Name", style="bold white")
    table.add_column("Kitta", justify="right", style="yellow")
    table.add_column("CRN", style="dim")
    
    for idx, member in enumerate(members, 1):
        table.add_row(str(idx), member['name'], str(member['applied_kitta']), member['crn_number'])
    
    console.print(table)
    
    # Confirmation AFTER showing the list
    confirm = input(f"\n⚠️  Apply IPO for ALL {len(members)} members shown above? (yes/no): ").strip().lower()
    if confirm != 'yes':
        console.print("[bold red]✗ Operation cancelled[/bold red]\n")
        return
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        
        try:
            # ========== PHASE 1: CREATE TABS & LOGIN ALL MEMBERS ==========
            console.print()
            console.print(Rule("[bold cyan]PHASE 1: MULTI-TAB LOGIN (ALL MEMBERS)[/bold cyan]"))
            console.print()
            
            pages_data = []
            
            # Create tabs and login sequentially (but keep all tabs open)
            console.print(f"[bold]🚀 Opening {len(members)} tabs and logging in...[/bold]\n")
            
            for idx, member in enumerate(members, 1):
                member_name = member['name']
                page = context.new_page()
                
                try:
                    console.print(f"[cyan][Tab {idx}][/cyan] Starting login for: [bold]{member_name}[/bold]")
                    
                    # Navigate
                    page.goto("https://meroshare.cdsc.com.np/#/login", wait_until="networkidle")
                    time.sleep(2)
                    
                    # Select DP
                    page.click("span.select2-selection")
                    time.sleep(1)
                    page.wait_for_selector(".select2-results", timeout=5000)
                    
                    search_box = page.query_selector("input.select2-search__field")
                    if search_box:
                        search_box.type(member['dp_value'])
                        time.sleep(0.5)
                        first_result = page.query_selector("li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']")
                        if first_result:
                            first_result.click()
                        else:
                            page.keyboard.press("Enter")
                    time.sleep(1)
                    
                    # Fill username
                    username_selectors = [
                        "input[formcontrolname='username']",
                        "input#username",
                        "input[placeholder*='User']"
                    ]
                    for selector in username_selectors:
                        try:
                            page.fill(selector, member['username'], timeout=2000)
                            break
                        except:
                            continue
                    
                    # Fill password
                    password_selectors = [
                        "input[formcontrolname='password']",
                        "input[type='password']"
                    ]
                    for selector in password_selectors:
                        try:
                            page.fill(selector, member['password'], timeout=2000)
                            break
                        except:
                            continue
                    
                    # Click login
                    login_button_selectors = [
                        "button.btn.sign-in",
                        "button[type='submit']",
                        "button:has-text('Login')"
                    ]
                    for selector in login_button_selectors:
                        try:
                            page.click(selector, timeout=2000)
                            break
                        except:
                            continue
                    
                    # Wait for login
                    try:
                        page.wait_for_function("window.location.hash !== '#/login'", timeout=8000)
                        time.sleep(2)
                    except:
                        time.sleep(2)
                    
                    # Check if logged in
                    if "#/login" not in page.url.lower():
                        console.print(f"[green]✓ [Tab {idx}] Login successful: {member_name}[/green]")
                        pages_data.append({"success": True, "member": member, "page": page, "tab_index": idx})
                    else:
                        console.print(f"[red]✗ [Tab {idx}] Login failed: {member_name}[/red]")
                        pages_data.append({"success": False, "member": member, "page": page, "tab_index": idx, "error": "Login failed"})
                        
                except Exception as e:
                    console.print(f"[red]✗ [Tab {idx}] Error logging in {member_name}: {e}[/red]")
                    pages_data.append({"success": False, "member": member, "page": page, "tab_index": idx, "error": str(e)})
            
            # Summary of login phase
            successful_logins = [p for p in pages_data if p['success']]
            failed_logins = [p for p in pages_data if not p['success']]
            
            console.print()
            summary_table = Table(title=f"Login Summary ({len(successful_logins)}/{len(members)} successful)", box=box.ROUNDED)
            summary_table.add_column("Member", style="white")
            summary_table.add_column("Status", style="bold")
            summary_table.add_column("Message", style="dim")
            
            for p in successful_logins:
                summary_table.add_row(p['member']['name'], "[green]Success[/green]", "-")
            for p in failed_logins:
                summary_table.add_row(p['member']['name'], "[red]Failed[/red]", p.get('error', 'Unknown error'))
            
            console.print(summary_table)
            
            if not successful_logins:
                console.print("[bold red]\n✗ No successful logins. Exiting...[/bold red]")
                return
            
            # Continue with successful logins only
            if failed_logins:
                proceed = input(f"\n⚠ {len(failed_logins)} login(s) failed. Continue with {len(successful_logins)} member(s)? (yes/no): ").strip().lower()
                if proceed != 'yes':
                    console.print("[red]✗ Operation cancelled[/red]")
                    return
            
            # ========== PHASE 2: SEQUENTIAL IPO APPLICATION ==========
            console.print()
            console.print(Rule("[bold cyan]PHASE 2: IPO APPLICATION (SEQUENTIAL)[/bold cyan]"))
            console.print()
            
            # Use first successful login to select IPO
            first_page = successful_logins[0]['page']
            
            console.print("Navigating to IPO page to select IPO...")
            first_page.goto("https://meroshare.cdsc.com.np/#/asba", wait_until="networkidle")
            time.sleep(3)
            
            console.print("Fetching available IPOs...\n")
            
            # Check if there are any IPOs available
            try:
                first_page.wait_for_selector(".company-list", timeout=10000)
                time.sleep(2)
            except Exception as e:
                console.print("[bold yellow]⚠ No IPOs currently available on Meroshare[/bold yellow]")
                console.print("[red]✗ Cannot proceed with IPO application[/red]\n")
                
                # Check if there's a "no data" message
                try:
                    no_data = first_page.query_selector("text=No Data Available")
                    if no_data:
                        console.print("→ Meroshare shows: 'No Data Available'")
                except:
                    pass
                
                first_page.screenshot(path="no_ipos_available.png")
                console.print("[dim]📸 Screenshot saved: no_ipos_available.png[/dim]\n")
                
                if not headless:
                    console.print("Browser will stay open for 20 seconds...")
                    time.sleep(20)
                
                return
            
            company_rows = first_page.query_selector_all(".company-list")
            
            available_ipos = []
            for idx, row in enumerate(company_rows, 1):
                try:
                    company_name_elem = row.query_selector(".company-name span")
                    share_type_elem = row.query_selector(".share-of-type")
                    share_group_elem = row.query_selector(".isin")
                    
                    if company_name_elem and share_type_elem and share_group_elem:
                        company_name = company_name_elem.inner_text().strip()
                        share_type = share_type_elem.inner_text().strip()
                        share_group = share_group_elem.inner_text().strip()
                        
                        if "ipo" in share_type.lower() and "ordinary" in share_group.lower():
                            available_ipos.append({
                                "index": len(available_ipos) + 1,
                                "company_name": company_name,
                                "share_type": share_type,
                                "share_group": share_group
                            })
                except Exception as e:
                    pass
            
            if not available_ipos:
                console.print("[bold red]✗ No IPOs available to apply![/bold red]")
                return
            
            ipo_table = Table(title="Available IPOs (Ordinary Shares)", box=box.ROUNDED)
            ipo_table.add_column("No.", justify="right", style="cyan")
            ipo_table.add_column("Company", style="bold white")
            ipo_table.add_column("Type", style="yellow")
            ipo_table.add_column("Group", style="dim")
            
            for ipo in available_ipos:
                ipo_table.add_row(str(ipo['index']), ipo['company_name'], ipo['share_type'], ipo['share_group'])
            
            console.print(ipo_table)
            
            if not headless:
                selection = input(f"\nSelect IPO to apply for all members (1-{len(available_ipos)}): ").strip()
                try:
                    selected_idx = int(selection) - 1
                    if selected_idx < 0 or selected_idx >= len(available_ipos):
                        console.print("[red]✗ Invalid selection![/red]")
                        return
                except ValueError:
                    console.print("[red]✗ Invalid input![/red]")
                    return
            else:
                selected_idx = 0
            
            selected_ipo = available_ipos[selected_idx]
            console.print(Panel(f"[bold green]✓ Selected IPO: {selected_ipo['company_name']}[/bold green]\n[yellow]⚠ Will apply this IPO for {len(successful_logins)} member(s)[/yellow]", box=box.ROUNDED))
            
            # Apply IPO for each member sequentially
            application_results = []
            
            for page_data in successful_logins:
                member = page_data['member']
                page = page_data['page']
                tab_index = page_data['tab_index']
                member_name = member['name']
                
                console.print()
                console.print(Rule(f"[Tab {tab_index}] APPLYING FOR: {member_name}"))
                
                try:
                    # Navigate to ASBA
                    console.print(f"[cyan][Tab {tab_index}][/cyan] Navigating to IPO page...")
                    page.goto("https://meroshare.cdsc.com.np/#/asba", wait_until="networkidle")
                    time.sleep(3)
                    
                    # Find and click the IPO
                    page.wait_for_selector(".company-list", timeout=10000)
                    time.sleep(2)
                    
                    company_rows = page.query_selector_all(".company-list")
                    ipo_found = False
                    already_applied = False
                    
                    for row in company_rows:
                        try:
                            company_name_elem = row.query_selector(".company-name span")
                            if company_name_elem and selected_ipo['company_name'] in company_name_elem.inner_text():
                                apply_button = row.query_selector("button.btn-issue")
                                if apply_button:
                                    # Check button text to see if already applied (shows 'Edit')
                                    button_text = apply_button.inner_text().strip().lower()
                                    
                                    if "edit" in button_text or "view" in button_text:
                                        console.print(f"[yellow][Tab {tab_index}] ⚠ IPO already applied (button shows: '{button_text.title()}')[/yellow]")
                                        already_applied = True
                                        ipo_found = True
                                        break
                                    else:
                                        console.print(f"[cyan][Tab {tab_index}][/cyan] Clicking Apply button (button shows: '{button_text.title()}')...")
                                        apply_button.click()
                                        ipo_found = True
                                        break
                        except:
                            continue
                    
                    if not ipo_found:
                        raise Exception("IPO not found in the list")
                    
                    if already_applied:
                        console.print(f"[green]✓ [Tab {tab_index}] Skipping - IPO already applied for {member_name}[/green]")
                        application_results.append({"member": member_name, "success": True, "status": "already_applied"})
                        continue
                    
                    time.sleep(3)
                    
                    # Fill form
                    console.print(f"[cyan][Tab {tab_index}][/cyan] Filling application form...")
                    page.wait_for_selector("select#selectBank", timeout=10000)
                    time.sleep(2)
                    
                    # Select bank
                    bank_options = page.query_selector_all("select#selectBank option")
                    valid_banks = [opt for opt in bank_options if opt.get_attribute("value")]
                    if valid_banks:
                        page.select_option("select#selectBank", valid_banks[0].get_attribute("value"))
                    time.sleep(2)
                    
                    # Select account
                    page.wait_for_selector("select#accountNumber", timeout=5000)
                    account_options = page.query_selector_all("select#accountNumber option")
                    valid_accounts = [opt for opt in account_options if opt.get_attribute("value")]
                    if valid_accounts:
                        page.select_option("select#accountNumber", valid_accounts[0].get_attribute("value"))
                    time.sleep(2)
                    
                    # Fill kitta
                    console.print(f"[cyan][Tab {tab_index}][/cyan] Kitta: [bold]{member['applied_kitta']}[/bold]")
                    page.fill("input#appliedKitta", str(member['applied_kitta']))
                    time.sleep(1)
                    
                    # Fill CRN
                    console.print(f"[cyan][Tab {tab_index}][/cyan] CRN: [dim]{member['crn_number']}[/dim]")
                    page.fill("input#crnNumber", member['crn_number'])
                    time.sleep(1)
                    
                    # Accept disclaimer
                    disclaimer_checkbox = page.query_selector("input#disclaimer")
                    if disclaimer_checkbox:
                        disclaimer_checkbox.check()
                    time.sleep(1)
                    
                    # Click proceed
                    console.print(f"[cyan][Tab {tab_index}][/cyan] Clicking Proceed...")
                    proceed_button = page.query_selector("button.btn-primary[type='submit']")
                    if proceed_button:
                        proceed_button.click()
                    time.sleep(3)
                    
                    # Enter PIN
                    console.print(f"[cyan][Tab {tab_index}][/cyan] Entering transaction PIN...")
                    page.wait_for_selector("input#transactionPIN", timeout=10000)
                    time.sleep(2)
                    page.fill("input#transactionPIN", member['transaction_pin'])
                    time.sleep(2)
                    
                    # Submit
                    console.print(f"[cyan][Tab {tab_index}][/cyan] Submitting application...")
                    clicked = False
                    
                    # Try multiple methods to click Apply button
                    try:
                        apply_buttons = page.query_selector_all("button:has-text('Apply')")
                        for btn in apply_buttons:
                            if btn.is_visible() and not btn.is_disabled():
                                btn.click()
                                clicked = True
                                break
                    except:
                        pass
                    
                    if not clicked:
                        try:
                            submit_button = page.query_selector("div.confirm-page-btn button.btn-primary[type='submit']")
                            if submit_button and submit_button.is_visible():
                                submit_button.click()
                                clicked = True
                        except:
                            pass
                    
                    if not clicked:
                        try:
                            page.evaluate("""
                                const buttons = document.querySelectorAll('button');
                                for (const btn of buttons) {
                                    if (btn.textContent.includes('Apply') && btn.type === 'submit') {
                                        btn.click();
                                        break;
                                    }
                                }
                            """)
                            clicked = True
                        except:
                            pass
                    
                    if not clicked:
                        raise Exception("Failed to click submit button")
                    
                    time.sleep(5)
                    
                    console.print(f"[bold green]✓ [Tab {tab_index}] Application submitted for {member_name}![/bold green]")
                    application_results.append({"member": member_name, "success": True})
                    
                except Exception as e:
                    console.print(f"[bold red]✗ [Tab {tab_index}] Failed for {member_name}: {e}[/bold red]")
                    application_results.append({"member": member_name, "success": False, "error": str(e)})
                    page.screenshot(path=f"error_{member_name}.png")
            
            # ========== FINAL SUMMARY ==========
            console.print()
            
            successful_apps = [r for r in application_results if r['success']]
            failed_apps = [r for r in application_results if not r['success']]
            
            final_table = Table(title=f"Final Application Summary: {selected_ipo['company_name']}", box=box.ROUNDED)
            final_table.add_column("Member", style="white")
            final_table.add_column("Status", style="bold")
            final_table.add_column("Details", style="dim")
            
            for r in successful_apps:
                status = "[yellow]Already Applied[/yellow]" if r.get('status') == 'already_applied' else "[green]Success[/green]"
                details = "Skipped" if r.get('status') == 'already_applied' else "Applied Successfully"
                final_table.add_row(r['member'], status, details)
                
            for r in failed_apps:
                final_table.add_row(r['member'], "[red]Failed[/red]", r.get('error', 'Unknown error'))
                
            console.print(final_table)
            
            if not headless:
                console.print("\n[dim]Browser will stay open for 60 seconds for verification...[/dim]")
                time.sleep(60)
            
        except Exception as e:
            console.print(f"\n[bold red]✗ Critical error: {e}[/bold red]")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

def get_dp_list():
    """Fetch and display available DP list with values from API"""
    import requests
    
    try:
        with console.status("[bold green]Fetching DP list from Meroshare API...", spinner="dots"):
            # Fetch data from API
            response = requests.get("https://webbackend.cdsc.com.np/api/meroShare/capital/")
            response.raise_for_status()
            
            dp_data = response.json()
            
            # Sort by name for better readability
            dp_data.sort(key=lambda x: x['name'])
        
        table = Table(title=f"Available Depository Participants (Total: {len(dp_data)})", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("ID", style="bold yellow", justify="right")
        table.add_column("Code", style="dim")
        table.add_column("Name", style="white")
        
        for dp in dp_data:
            table.add_row(str(dp['id']), str(dp['code']), dp['name'])
            
        console.print(table)
        console.print(Panel("Note: Use the [bold yellow]ID[/] (first column) when setting up credentials\n(e.g., 139 for CREATIVE SECURITIES)", box=box.ROUNDED, style="dim"))
        
    except requests.RequestException as e:
        console.print(f"[bold red]✗ Error fetching DP list from API:[/bold red] {e}")
        console.print("  Please check your internet connection.\n")
    except Exception as e:
        console.print(f"[bold red]✗ Unexpected error:[/bold red] {e}\n")

# ============================================
# Market Data Command Functions  
# ============================================

def format_number(num):
    """Format large numbers with K, M, B suffixes"""
    try:
        num = float(str(num).replace(',', ''))
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.2f}K"
        else:
            return f"{num:.2f}"
    except (ValueError, AttributeError):
        return str(num)

def format_rupees(amount):
    """Format amount as rupees with proper comma placement"""
    try:
        amount = float(str(amount).replace(',', ''))
        return f"Rs. {amount:,.2f}"
    except (ValueError, AttributeError):
        return f"Rs. {amount}"

def get_ss_time():
    """Get timestamp from ShareSansar market summary"""
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

def cmd_ipo():
    """Display all open IPOs/public offerings"""
    try:
        with console.status("[bold green]Fetching open IPOs...", spinner="dots"):
            response = requests.get(
                "https://sharehubnepal.com/data/api/v1/public-offering",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        
        if not data.get('success'):
            console.print(Panel("⚠️  Unable to fetch IPO data. API request failed.", style="bold red", box=box.ROUNDED))
            return
        
        all_ipos = data.get('data', {}).get('content', [])

        def _is_general_public(ipo_item):
            """Return True if the IPO is for the general public."""
            try:
                f = str(ipo_item.get('for', '')).lower()
            except Exception:
                return False
            return 'general' in f and 'public' in f

        # Filter to only open IPOs that are for the general public
        open_ipos = [ipo for ipo in all_ipos if ipo.get('status') == 'Open' and _is_general_public(ipo)]
        
        if not open_ipos:
            console.print(Panel("💤 No IPOs are currently open for subscription.", style="bold yellow", box=box.ROUNDED))
            return
        
        table = Table(title=f"📈 Open IPOs ({len(open_ipos)})", box=box.ROUNDED, header_style="bold cyan", expand=True)
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
            
            days_left = None
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
        console.print(Panel("💡 Tip: Use [bold cyan]nepse apply[/] to apply for IPO via Meroshare", box=box.ROUNDED, style="dim"))
        
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]🔌 Connection Error:[/bold red] Unable to connect to API.\n{str(e)[:100]}\n")
    except Exception as e:
        console.print(f"[bold red]⚠️  Error:[/bold red] {str(e)[:200]}\n")

def cmd_nepse():
    """Display NEPSE indices data"""
    try:
        with console.status("[bold green]Fetching NEPSE indices...", spinner="dots"):
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            url = "https://nepsealpha.com/live/stocks"
            response = scraper.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        
        # Get all indices from stock_live.prices where type is 'index'
        prices = data.get('stock_live', {}).get('prices', [])
        indices = [item for item in prices if item.get('stockinfo', {}).get('type') == 'index']
        
        if not indices:
            console.print(Panel("⚠️  No index data available.", style="bold yellow", box=box.ROUNDED))
            return
        
        # Get timestamp
        timestamp = data.get('stock_live', {}).get('asOf', 'N/A')
        
        table = Table(title=f"NEPSE Index Data (Live) - {timestamp}", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("Index", style="bold white")
        table.add_column("Close", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("% Change", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("Range", justify="center", style="dim")
        table.add_column("Turnover", justify="right")
        
        for item in indices:
            index_name = item.get('symbol', 'N/A')
            close_val = item.get('close', 0)
            pct_change = item.get('percent_change', 0)
            low_val = item.get('low', 0)
            high_val = item.get('high', 0)
            turnover = item.get('volume', 0)  # Using volume as turnover
            
            # Calculate point change
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
            
            table.add_row(
                index_name,
                f"{close_val:,.2f}",
                f"[{color}]{point_change:+,.2f}[/{color}]",
                f"[{color}]{pct_change:+.2f}%[/{color}]",
                f"[{color}]{trend_icon}[/{color}]",
                range_str,
                format_number(turnover)
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error fetching NEPSE data:[/bold red] {str(e)}\n")

def cmd_subidx(subindex_name):
    """Display sub-index details"""
    try:
        subindex_name = subindex_name.upper()
        
        # Mapping user-friendly names to API symbols
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
        
        with console.status(f"[bold green]Fetching {subindex_name} sub-index data...", spinner="dots"):
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            response = scraper.get("https://nepsealpha.com/live/stocks", timeout=10)
            response.raise_for_status()
            data = response.json()
        
        # Get the mapped symbol
        search_symbol = sub_index_mapping.get(subindex_name, subindex_name)
        
        # Get all indices from stock_live.prices
        prices = data.get('stock_live', {}).get('prices', [])
        indices = [item for item in prices if item.get('stockinfo', {}).get('type') == 'index']
        
        # Find the specific sub-index
        sub_index_data = None
        for item in indices:
            if item.get('symbol', '').upper() == search_symbol.upper():
                sub_index_data = item
                break
        
        if not sub_index_data:
            console.print(Panel(f"⚠️  Sub-index '{subindex_name}' not found.", style="bold red", box=box.ROUNDED))
            
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
        
        # Get sector full name from sectors mapping
        sectors = data.get('sectors', {})
        sector_full_name = sectors.get(search_symbol, search_symbol)
        
        close_val = sub_index_data.get('close', 0)
        pct_change = sub_index_data.get('percent_change', 0)
        low_val = sub_index_data.get('low', 0)
        high_val = sub_index_data.get('high', 0)
        open_val = sub_index_data.get('open', 0)
        turnover = sub_index_data.get('volume', 0)
        
        # Calculate point change
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
        
        # Create a grid layout for the details
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

def scrape_sharesansar_market_summary(headless: bool = True) -> dict:
    """
    Scrape comprehensive market summary from ShareSansar.
    Returns a dict with:
    - sector_turnover: dict[sector_name, turnover]
    - top_turnovers: list[dict]
    - top_traded: list[dict]
    - top_transactions: list[dict]
    - top_brokers: list[dict]
    - as_of: str
    """
    result = {
        "sector_turnover": {},
        "top_turnovers": [],
        "top_traded": [],
        "top_transactions": [],
        "top_brokers": [],
        "as_of": "N/A"
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.on("console", lambda msg: None)
            
            try:
                page.goto("https://www.sharesansar.com/market", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("table", timeout=20000)
            except:
                browser.close()
                return result
            
            # Extract all data in one go
            data = page.evaluate("""
                () => {
                    const result = {
                        sector_turnover: [],
                        top_turnovers: [],
                        top_traded: [],
                        top_transactions: [],
                        top_brokers: [],
                        as_of: ""
                    };
                    
                    const findTableByHeading = (searchText) => {
                        const headings = document.querySelectorAll('h3, h4');
                        for (const h of headings) {
                            if (h.innerText.includes(searchText)) {
                                let next = h.nextElementSibling;
                                while (next) {
                                    if (next.tagName === 'TABLE') return next;
                                    if (next.querySelector('table')) return next.querySelector('table');
                                    next = next.nextElementSibling;
                                }
                            }
                        }
                        return null;
                    };
                    
                    // 1. Sector Turnover
                    const subIndicesTable = findTableByHeading('Sub Indices');
                    if (subIndicesTable) {
                        const rows = subIndicesTable.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 8) {
                                result.sector_turnover.push({
                                    name: cells[0].innerText.trim(),
                                    turnover: cells[cells.length - 1].innerText.trim()
                                });
                            }
                        });
                    }
                    
                    // 2. Top Turnovers
                    const topTurnoverTable = findTableByHeading('Top TurnOvers');
                    if (topTurnoverTable) {
                        const rows = topTurnoverTable.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 3) {
                                result.top_turnovers.push({
                                    symbol: cells[0].innerText.trim(),
                                    turnover: cells[1].innerText.trim(),
                                    ltp: cells[2].innerText.trim()
                                });
                            }
                        });
                    }
                    
                    // 3. Top Traded Shares
                    const topTradedTable = findTableByHeading('Top Traded Shares');
                    if (topTradedTable) {
                        const rows = topTradedTable.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 3) {
                                result.top_traded.push({
                                    symbol: cells[0].innerText.trim(),
                                    volume: cells[1].innerText.trim(),
                                    ltp: cells[2].innerText.trim()
                                });
                            }
                        });
                    }
                    
                    // 4. Top Transactions
                    const topTransTable = findTableByHeading('Top Traded Transactions');
                    if (topTransTable) {
                        const rows = topTransTable.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 3) {
                                result.top_transactions.push({
                                    symbol: cells[0].innerText.trim(),
                                    transactions: cells[1].innerText.trim(),
                                    ltp: cells[2].innerText.trim()
                                });
                            }
                        });
                    }
                    
                    // 5. Top Brokers
                    const topBrokersTable = findTableByHeading('Top Brokers');
                    if (topBrokersTable) {
                        const rows = topBrokersTable.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 4) {
                                result.top_brokers.push({
                                    broker: cells[0].innerText.trim(),
                                    purchase: cells[1].innerText.trim(),
                                    sales: cells[2].innerText.trim(),
                                    total: cells[3].innerText.trim()
                                });
                            }
                        });
                    }
                    
                    // 6. Date
                    const paragraphs = document.querySelectorAll('p');
                    for (const p of paragraphs) {
                        if (p.innerText.includes('As of')) {
                            result.as_of = p.innerText.trim().replace('As of', '').trim();
                            break;
                        }
                    }
                    
                    return result;
                }
            """)
            
            # Process Sector Turnover into dict
            for item in data['sector_turnover']:
                name = item['name']
                turnover_str = item['turnover'].replace(',', '')
                try:
                    result['sector_turnover'][name] = float(turnover_str)
                except ValueError:
                    pass
                    
            result['top_turnovers'] = data['top_turnovers']
            result['top_traded'] = data['top_traded']
            result['top_transactions'] = data['top_transactions']
            result['top_brokers'] = data['top_brokers']
            result['as_of'] = data['as_of']
            
            browser.close()
            
    except Exception:
        pass
            
    return result

def cmd_mktsum():
    """Display comprehensive market summary using hybrid data (ShareHub + ShareSansar)"""
    try:
        sharehub_data = None
        sharesansar_data = {}
        
        with console.status("[bold green]Fetching market data...", spinner="dots"):
            # 1. Fetch ShareHub Data
            try:
                url = "https://sharehubnepal.com/live/api/v2/nepselive/home-page-data"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    sharehub_data = response.json()
            except Exception as e:
                console.print(f"[red]⚠️  API request failed: {e}[/red]")
            
            if not sharehub_data:
                return

            # 2. Scrape ShareSansar Market Summary
            sharesansar_data = scrape_sharesansar_market_summary(headless=True)
            
        # Process Data
        indices = sharehub_data.get("indices", [])
        nepse_index = next((i for i in indices if i.get("symbol") == "NEPSE"), {})
        
        if not nepse_index:
            console.print("[red]⚠️  NEPSE index data not found.[/red]")
            return
            
        # Extract NEPSE Info
        current_price = float(nepse_index.get('currentValue', 0))
        daily_gain = float(nepse_index.get('changePercent', 0))
        
        # Get Total Turnover
        market_summary = sharehub_data.get("marketSummary", [])
        turnover_item = next((i for i in market_summary if "Turnover" in i.get("name", "")), {})
        turnover = float(turnover_item.get('value', 0))
        
        # Get Trading Activity
        stock_summary = sharehub_data.get("stockSummary", {})
        positive_stocks = stock_summary.get("advanced", 0)
        negative_stocks = stock_summary.get("declined", 0)
        unchanged_stocks = stock_summary.get("unchanged", 0)
        positive_circuit = stock_summary.get("positiveCircuit", 0)
        negative_circuit = stock_summary.get("negativeCircuit", 0)
        total_traded = positive_stocks + negative_stocks + unchanged_stocks
        
        # Display Logic
        color = "green" if daily_gain > 0 else "red" if daily_gain < 0 else "yellow"
        trend_icon = "▲" if daily_gain > 0 else "▼" if daily_gain < 0 else "•"
        
        # Main NEPSE Panel
        nepse_grid = Table.grid(expand=True, padding=(0, 2))
        nepse_grid.add_column(style="bold white")
        nepse_grid.add_column(justify="right")
        
        nepse_grid.add_row("Current Index", f"{current_price:,.2f}")
        nepse_grid.add_row("Daily Gain", f"[{color}]{daily_gain:+.2f}% {trend_icon}[/{color}]")
        nepse_grid.add_row("Turnover", format_number(turnover))
        
        nepse_panel = Panel(
            nepse_grid,
            title=f"[bold {color}]NEPSE INDEX[/]",
            box=box.ROUNDED,
            border_style=color
        )
        
        # Trading Activity Panel
        activity_grid = Table.grid(expand=True, padding=(0, 2))
        activity_grid.add_column(style="bold white")
        activity_grid.add_column(justify="right")
        
        activity_grid.add_row("Positive Stocks", f"[green]{positive_stocks}[/green]")
        activity_grid.add_row("Negative Stocks", f"[red]{negative_stocks}[/red]")
        activity_grid.add_row("Unchanged", f"[yellow]{unchanged_stocks}[/yellow]")
        activity_grid.add_row("Positive Circuit", f"[bright_green]{positive_circuit}[/bright_green]")
        activity_grid.add_row("Negative Circuit", f"[bright_red]{negative_circuit}[/bright_red]")
        activity_grid.add_row("Total Traded", f"[bold]{total_traded}[/bold]")
        
        activity_panel = Panel(
            activity_grid,
            title="[bold cyan]TRADING ACTIVITY[/]",
            box=box.ROUNDED,
            border_style="cyan"
        )
        
        console.print(Columns([nepse_panel, activity_panel]))
        
        # Display Date and Notice
        date_str = sharesansar_data.get('as_of', 'N/A')
        console.print(f"\n[bold cyan]📅 Market Data as of:[/] [yellow]{date_str}[/yellow]")
        console.print("[dim italic]ℹ️  Note: Market summary data will be updated after market closes[/dim italic]\n")
        
        # Sector Table
        table = Table(title="Sector Performance", box=box.ROUNDED, expand=True)
        table.add_column("Sector", style="cyan")
        table.add_column("Current", justify="right")
        table.add_column("Change %", justify="right")
        table.add_column("Turnover", justify="right")
        
        # Normalize ShareSansar keys
        normalized_turnover = {}
        sector_turnover_data = sharesansar_data.get('sector_turnover', {})
        for k, v in sector_turnover_data.items():
            clean_k = k.replace("SubIndex", "").replace("Index", "").replace("And", "&").strip().lower()
            normalized_turnover[clean_k] = v
            
        sub_indices = sharehub_data.get("subIndices", [])
        for sector in sub_indices:
            name = sector.get("name", "Unknown")
            price = sector.get("currentValue", 0)
            change = sector.get("changePercent", 0)
            
            # Match turnover
            clean_name = name.replace("And", "&").strip().lower()
            sector_turnover = 0
            
            if clean_name in normalized_turnover:
                sector_turnover = normalized_turnover[clean_name]
            elif clean_name == "banking" and "banking" in normalized_turnover:
                sector_turnover = normalized_turnover["banking"]
            elif clean_name == "development bank" and "development bank" in normalized_turnover:
                sector_turnover = normalized_turnover["development bank"]
            elif clean_name == "finance" and "finance" in normalized_turnover:
                sector_turnover = normalized_turnover["finance"]
            elif clean_name == "hydropower" and "hydropower" in normalized_turnover:
                sector_turnover = normalized_turnover["hydropower"]
            elif clean_name == "life insurance" and "life insurance" in normalized_turnover:
                sector_turnover = normalized_turnover["life insurance"]
            elif clean_name == "microfinance" and "microfinance" in normalized_turnover:
                sector_turnover = normalized_turnover["microfinance"]
            elif clean_name == "mutual fund" and "mutual fund" in normalized_turnover:
                sector_turnover = normalized_turnover["mutual fund"]
            elif clean_name == "non life insurance" and "non life insurance" in normalized_turnover:
                sector_turnover = normalized_turnover["non life insurance"]
            elif clean_name == "others" and "others" in normalized_turnover:
                sector_turnover = normalized_turnover["others"]
            elif clean_name == "trading" and "trading" in normalized_turnover:
                sector_turnover = normalized_turnover["trading"]
            
            sec_color = "green" if change > 0 else "red" if change < 0 else "white"
            
            table.add_row(
                name,
                f"{price:,.2f}",
                f"[{sec_color}]{change:+.2f}%[/{sec_color}]",
                format_number(sector_turnover) if sector_turnover > 0 else "N/A"
            )
            
        console.print(table)
        
        # Display Top Lists
        top_turnovers = sharesansar_data.get('top_turnovers', [])
        top_traded = sharesansar_data.get('top_traded', [])
        top_transactions = sharesansar_data.get('top_transactions', [])
        top_brokers = sharesansar_data.get('top_brokers', [])
        
        if top_turnovers or top_traded or top_transactions:
            console.print("\n")
            
            # Top Turnovers Table
            if top_turnovers:
                turnover_table = Table(title="📊 Top Turnovers", box=box.ROUNDED, show_header=True)
                turnover_table.add_column("Symbol", style="bold cyan")
                turnover_table.add_column("Turnover (Rs)", justify="right")
                turnover_table.add_column("LTP (Rs)", justify="right", style="dim")
                
                for item in top_turnovers:
                    turnover_table.add_row(
                        item.get('symbol', 'N/A'),
                        item.get('turnover', 'N/A'),
                        item.get('ltp', 'N/A')
                    )
            
            # Top Traded Table
            if top_traded:
                traded_table = Table(title="📈 Top Traded Shares", box=box.ROUNDED, show_header=True)
                traded_table.add_column("Symbol", style="bold cyan")
                traded_table.add_column("Volume", justify="right")
                traded_table.add_column("LTP (Rs)", justify="right", style="dim")
                
                for item in top_traded:
                    traded_table.add_row(
                        item.get('symbol', 'N/A'),
                        item.get('volume', 'N/A'),
                        item.get('ltp', 'N/A')
                    )
            
            # Top Transactions Table
            if top_transactions:
                trans_table = Table(title="🔁 Top Transactions", box=box.ROUNDED, show_header=True)
                trans_table.add_column("Symbol", style="bold cyan")
                trans_table.add_column("Transactions", justify="right")
                trans_table.add_column("LTP (Rs)", justify="right", style="dim")
                
                for item in top_transactions:
                    trans_table.add_row(
                        item.get('symbol', 'N/A'),
                        item.get('transactions', 'N/A'),
                        item.get('ltp', 'N/A')
                    )
            
            # Display in columns
            if top_turnovers and top_traded and top_transactions:
                console.print(Columns([turnover_table, traded_table, trans_table]))
            
        # Top Brokers Table
        if top_brokers:
            console.print("\n")
            broker_table = Table(title="🏢 Top Brokers", box=box.ROUNDED, show_header=True, expand=True)
            broker_table.add_column("Broker #", style="bold yellow", width=10)
            broker_table.add_column("Purchase (Rs)", justify="right")
            broker_table.add_column("Sales (Rs)", justify="right")
            broker_table.add_column("Total (Rs)", justify="right", style="bold green")
            
            for item in top_brokers:
                broker_table.add_row(
                    item.get('broker', 'N/A'),
                    item.get('purchase', 'N/A'),
                    item.get('sales', 'N/A'),
                    item.get('total', 'N/A')
                )
            
            console.print(broker_table)
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error:[/bold red] {str(e)}\n")

def cmd_topgl():
    """Display top 10 gainers and losers"""
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
        g_table = Table(title="📈 TOP 10 GAINERS", box=box.ROUNDED, header_style="bold green", expand=True)
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
        l_table = Table(title="📉 TOP 10 LOSERS", box=box.ROUNDED, header_style="bold red", expand=True)
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

def cmd_stonk(stock_name):
    """Display stock details (information only - no charts/alerts)"""
    try:
        stock_name = stock_name.upper()
        with console.status(f"[bold green]Fetching details for {stock_name}...", spinner="dots"):
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            
            # Try NepseAlpha API first
            stock_price_data = None
            try:
                response = scraper.get('https://nepsealpha.com/live/stocks', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    prices = data.get('stock_live', {}).get('prices', [])
                    
                    for item in prices:
                        if item.get('symbol', '').upper() == stock_name:
                            stock_price_data = item
                            break
            except:
                pass
            
            # Fetch company details from ShareSansar
            company_details = {
                "sector": "N/A",
                "share_registrar": "N/A",
                "company_fullform": stock_name,
            }
            
            try:
                response2 = requests.get(
                    f"https://www.sharesansar.com/company/{stock_name}", timeout=10)
                
                if response2.status_code == 200:
                    soup2 = BeautifulSoup(response2.text, "lxml")
                    all_rows = soup2.find_all("div", class_="row")
                    
                    if len(all_rows) >= 6:
                        info_row = all_rows[5]
                        second_row = info_row.find_all("div", class_="col-md-12")
                        if len(second_row) > 1:
                            shareinfo = second_row[1]
                            heading_list = shareinfo.find_all("h4")
                            
                            if len(heading_list) > 2:
                                company_details["sector"] = heading_list[1].find("span", class_="text-org").text
                                company_details["share_registrar"] = heading_list[2].find("span", class_="text-org").text
                    
                    company_full_form_tag = soup2.find(
                        "h1", style="color: #333;font-size: 20px;font-weight: 600;"
                    )
                    if company_full_form_tag is not None:
                        company_details["company_fullform"] = company_full_form_tag.text
            except:
                pass
            
            # Fallback to ShareSansar if NepseAlpha failed
            if not stock_price_data:
                try:
                    response_live = requests.get(
                        "https://www.sharesansar.com/live-trading", timeout=10)
                    
                    if response_live.status_code == 200:
                        soup = BeautifulSoup(response_live.text, "lxml")
                        stock_rows = soup.find_all("tr")
                        
                        for row in stock_rows[1:]:
                            row_data = row.find_all("td")
                            
                            if len(row_data) > 9 and row_data[1].text.strip() == stock_name:
                                close_price = float(row_data[2].text.strip().replace(',', ''))
                                pt_change = float(row_data[3].text.strip().replace(',', ''))
                                pct_change = row_data[4].text.strip()
                                
                                color = "green" if pt_change > 0 else "red" if pt_change < 0 else "yellow"
                                trend_icon = "▲" if pt_change > 0 else "▼" if pt_change < 0 else "•"
                                
                                grid = Table.grid(expand=True, padding=(0, 2))
                                grid.add_column(style="bold white")
                                grid.add_column(justify="right")
                                
                                grid.add_row("Last Traded Price", f"Rs. {row_data[2].text.strip()}")
                                grid.add_row("Change", f"[{color}]{row_data[3].text.strip()} ({pct_change}) {trend_icon}[/{color}]")
                                grid.add_row("Open", row_data[5].text.strip())
                                grid.add_row("High", row_data[6].text.strip())
                                grid.add_row("Low", row_data[7].text.strip())
                                grid.add_row("Volume", row_data[8].text.strip())
                                grid.add_row("Prev. Closing", row_data[9].text.strip())
                                grid.add_row("Sector", company_details['sector'])
                                grid.add_row("Share Registrar", company_details['share_registrar'])
                                
                                panel = Panel(
                                    grid,
                                    title=f"[bold {color}]{stock_name} — {company_details['company_fullform']}[/]",
                                    subtitle="Source: ShareSansar",
                                    box=box.ROUNDED,
                                    border_style=color
                                )
                                console.print(panel)
                                return
                except:
                    pass
                
                console.print(Panel(f"⚠️  Stock '{stock_name}' not found.", style="bold red", box=box.ROUNDED))
                return
            
            # Use NepseAlpha data
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
            grid.add_row("Sector", company_details['sector'])
            grid.add_row("Share Registrar", company_details['share_registrar'])
            
            panel = Panel(
                grid,
                title=f"[bold {color}]{stock_name} — {company_details['company_fullform']}[/]",
                subtitle=f"As of: {data.get('stock_live', {}).get('asOf', 'N/A')}",
                box=box.ROUNDED,
                border_style=color
            )
            console.print(panel)
        
    except Exception as e:
        console.print(f"[bold red]⚠️  Error fetching stock data:[/bold red] {str(e)}\n")

# ============================================
# Argument Parser and Command Metadata
# ============================================

# Category ordering for command palette
COMMAND_CATEGORY_ORDER = [
    "Market Data",
    "IPO Management",
    "Interactive Tools",
    "Configuration"
]

# Map commands to their categories
COMMAND_CATEGORY_MAP = {
    # Market Data
    "nepse": "Market Data",
    "subidx": "Market Data",
    "mktsum": "Market Data",
    "topgl": "Market Data",
    "stonk": "Market Data",
    
    # IPO Management
    "ipo": "IPO Management",
    "apply": "IPO Management",
    "status": "IPO Management",
    
    # Configuration
    "add-member": "Configuration",
    "list-members": "Configuration",
    "test-login": "Configuration",
    "get-portfolio": "Configuration",
    "dplist": "Configuration"
}

def build_parser():
    """Build the argument parser for the CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(
        prog="nepse",
        description="NEPSE CLI - Stock Market & IPO Automation Tool",
        epilog="Use 'nepse interactive' for an interactive command palette."
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Market Data Commands
    subparsers.add_parser("nepse", help="Display NEPSE indices")
    subparsers.add_parser("ipo", help="Show open IPOs")
    subparsers.add_parser("mktsum", help="Market summary")
    subparsers.add_parser("topgl", help="Top gainers and losers")
    
    subidx_parser = subparsers.add_parser("subidx", help="Sub-index details")
    subidx_parser.add_argument("name", help="Sub-index name (e.g., BANKING, HOTELS)")
    
    stonk_parser = subparsers.add_parser("stonk", help="Stock details")
    stonk_parser.add_argument("symbol", help="Stock symbol (e.g., NABIL)")
    
    # IPO Commands
    subparsers.add_parser("apply", help="Apply for IPO interactively")
    subparsers.add_parser("status", help="Check IPO application status")
    
    # Configuration Commands
    subparsers.add_parser("add-member", help="Add family member for IPO applications")
    subparsers.add_parser("list-members", help="List all family members")
    
    test_login_parser = subparsers.add_parser("test-login", help="Test login credentials")
    test_login_parser.add_argument("member_id", nargs="?", help="Member ID to test (optional)")
    
    portfolio_parser = subparsers.add_parser("get-portfolio", help="Get portfolio details")
    portfolio_parser.add_argument("member_id", nargs="?", help="Member ID (optional)")
    
    subparsers.add_parser("dplist", help="List available DPs")
    
    # Interactive Mode
    subparsers.add_parser("interactive", help="Launch interactive command palette")
    
    return parser

def get_command_metadata():
    """Return metadata for all commands (for interactive mode)"""
    return [
        # Market Data
        {"name": "nepse", "description": "Display NEPSE indices", "category": "Market Data"},
        {"name": "subidx <name>", "description": "Show sub-index details", "category": "Market Data"},
        {"name": "mktsum", "description": "Display market summary", "category": "Market Data"},
        {"name": "topgl", "description": "Show top gainers and losers", "category": "Market Data"},
        {"name": "stonk <symbol>", "description": "Show stock details", "category": "Market Data"},
        {"name": "ipo", "description": "List open IPOs", "category": "IPO Management"},
        
        # IPO Management
        {"name": "apply", "description": "Apply for IPO (use --gui for browser window)", "category": "IPO Management"},
        {"name": "apply-all", "description": "Apply IPO for all family members", "category": "IPO Management"},
        
        # Configuration
        {"name": "add", "description": "Add new family member", "category": "Configuration"},
        {"name": "list", "description": "List all family members", "category": "Configuration"},
        {"name": "edit", "description": "Edit existing family member", "category": "Configuration"},
        {"name": "delete", "description": "Delete family member", "category": "Configuration"},
        {"name": "manage", "description": "Member management menu", "category": "Configuration"},
        {"name": "login [name]", "description": "Test login for member", "category": "Configuration"},
        {"name": "portfolio [name]", "description": "Get portfolio for member", "category": "Configuration"},
        {"name": "dp-list", "description": "List available DPs", "category": "Configuration"},
        
        # Interactive
        {"name": "help", "description": "Show help information", "category": "Interactive Tools"},
        {"name": "exit", "description": "Exit the CLI", "category": "Interactive Tools"},
    ]

def print_logo():
    """Render the gradient welcome logo when interactive mode launches."""
    # Initialize colorama for Windows ANSI support
    colorama_init(autoreset=True)
    
    # Add some top margin/gap before the logo
    print("\n")
    
    logo_lines = [
        " ███╗   ██╗███████╗██████╗ ███████╗███████╗      ██████╗██╗     ██╗",
        " ████╗  ██║██╔════╝██╔══██╗██╔════╝██╔════╝     ██╔════╝██║     ██║",
        " ██╔██╗ ██║█████╗  ██████╔╝███████╗█████╗ █████╗██║     ██║     ██║",
        " ██║╚██╗██║██╔══╝  ██╔═══╝ ╚════██║██╔══╝ ╚════╝██║     ██║     ██║",
        " ██║ ╚████║███████╗██║     ███████║███████╗     ╚██████╗███████╗██║",
        " ╚═╝  ╚═══╝╚══════╝╚═╝     ╚══════╝╚══════╝      ╚═════╝╚══════╝╚═╝",
    ]
    
    # Gradient colors from bright green to dark green (RGB values)
    colors = [
        (0, 255, 0),    # Bright green
        (0, 230, 0),
        (0, 204, 0),
        (0, 179, 0),
        (0, 153, 0),
        (0, 128, 0),    # Dark green
    ]
    
    for idx, line in enumerate(logo_lines):
        r, g, b = colors[idx]
        # Use ANSI 24-bit true color escape codes
        print(f"\033[38;2;{r};{g};{b}m{line}\033[0m")


def fuzzy_filter_commands(commands: List[Dict[str, str]], query: str) -> List[Dict[str, str]]:
    if not query:
        return commands
    query_lower = query.lower()
    filtered: List[Dict[str, str]] = []
    for command in commands:
        haystack = f"{command['name']} {command['description']}".lower()
        if query_lower in haystack:
            filtered.append(command)
            continue
        ratio = difflib.SequenceMatcher(None, query_lower, command['name'].lower()).ratio()
        if ratio >= 0.6:
            filtered.append(command)
    return filtered


def display_command_palette(commands: List[Dict[str, str]], category_order: List[str], query: str = "") -> None:
    # Hack to fix Rich output when running inside prompt_toolkit's patch_stdout
    # We must temporarily restore the original stdout so Rich can detect the terminal properly
    from prompt_toolkit.patch_stdout import StdoutProxy
    original_stdout = sys.stdout
    if isinstance(sys.stdout, StdoutProxy):
        sys.stdout = sys.stdout.original_stdout

    try:
        filtered_commands = fuzzy_filter_commands(commands, query)
        if not filtered_commands:
            message = f"No commands match '{query}'" if query else "No commands available"
            console.print(Panel(Text(message, justify="center"), title="Available Commands", border_style="red"))
            return

        grouped: Dict[str, List[Dict[str, str]]] = {category: [] for category in category_order}
        for command in filtered_commands:
            grouped.setdefault(command['category'], []).append(command)

        sections = []
        for category in category_order:
            items = grouped.get(category) or []
            if not items:
                continue
            header = Text(category, style="bold green")
            table = Table.grid(expand=True)
            table.add_column(style="bold cyan", width=20)
            table.add_column()
            for item in items:
                table.add_row(item['name'], item['description'])
            sections.extend([header, table, Text("")])

        sections.append(Text("Type to search commands...", style="dim"))
        console.print(Panel(Group(*sections), title="Available Commands", border_style="green"))
    finally:
        # Restore the proxy
        sys.stdout = original_stdout


class NepseCommandCompleter(Completer):
    """
    Completer that supports:
    1. Normal command completion
    2. 'Gemini-style' search when starting with '/'
       - Shows command + description
       - Filters by both name and description
    """

    def __init__(self, metadata: List[Dict[str, str]]):
        self.metadata = metadata
        # Quick lookup for normal completion
        self.names = [m['name'] for m in metadata] + ["exit", "quit", "help", "?"]

    def get_completions(self, document, complete_event):  # type: ignore[override]
        text = document.text_before_cursor
        
        # Check if we are in "Search Mode" (starts with /)
        if text.startswith('/'):
            query = text[1:].lower() # Strip the leading /
            
            # Filter commands
            for cmd in self.metadata:
                name = cmd['name']
                desc = cmd.get('description', '')
                
                # Fuzzy-ish match: query in name OR query in description
                if query in name.lower() or query in desc.lower():
                    yield Completion(
                        name,
                        start_position=-len(query),
                        display=FormattedText([
                            ("class:completion-command", f"{name:<15}"),
                            ("class:completion-description", f"  {desc}")
                        ]),
                    )
            
            # Filter built-ins
            for builtin in ["exit", "quit", "help", "?"]:
                if query in builtin:
                     yield Completion(
                        builtin,
                        start_position=-len(query),
                        display=FormattedText([
                            ("class:completion-command", f"{builtin:<15}"),
                            ("class:completion-builtin", "  Built-in command")
                        ]),
                    )
        else:
            # Normal completion (first word)
            word = text.split(' ')[-1]
            for name in self.names:
                if name.startswith(word):
                    yield Completion(name, start_position=-len(word))


LEGACY_SHORTCUTS = {
    "1": "apply",
    "2": "add",
    "3": "list",
    "4": "portfolio",
    "5": "login",
    "6": "dp-list",
    "7": "apply-all",
    "8": "ipo",
    "9": "nepse",
    "10": "subidx",
    "11": "mktsum",
    "12": "topgl",
    "13": "stonk",
    "0": "exit",
}


def ensure_history_file() -> None:
    if not CLI_HISTORY_FILE.exists():
        CLI_HISTORY_FILE.touch()


def create_prompt_session(command_metadata: List[Dict[str, str]]) -> PromptSession:
    ensure_history_file()
    completer = NepseCommandCompleter(command_metadata)
    return PromptSession(
        history=FileHistory(str(CLI_HISTORY_FILE)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        complete_style=CompleteStyle.COLUMN,
        style=CLI_PROMPT_STYLE,
    )


def _resolve_member_by_name(member_name: str):
    config = load_family_members()
    for member in config.get('members', []):
        if member['name'].lower() == member_name.lower():
            return member
    return None


def execute_interactive_command(command: str, args: List[str], context: Dict[str, object]) -> bool:
    command = command.lower()
    if command in {"help", "?"}:
        display_command_palette(context['metadata'], context['category_order'])
        return True

    flag_args = [arg for arg in args if arg.startswith("--")]
    positional_args = [arg for arg in args if not arg.startswith("--")]
    gui_requested = "--gui" in flag_args
    headless = not gui_requested

    if command == "apply":
        context['apply_ipo'](auto_load=True, headless=headless)
        return True
    if command == "apply-all":
        context['apply_all'](headless=headless)
        return True
    if command == "add":
        context['add_member']()
        return True
    if command == "list":
        context['list_members']()
        return True
    if command == "edit":
        context['edit_member']()
        return True
    if command == "delete":
        context['delete_member']()
        return True
    if command == "manage":
        context['manage_members']()
        return True
    if command == "portfolio":
        member = None
        if positional_args:
            member = _resolve_member_by_name(positional_args[0])
            if not member:
                print(f"\n✗ Member '{positional_args[0]}' not found.")
        if not member:
            member = context['select_member']()
        if member:
            context['portfolio'](member, headless=headless)
        return True
    if command == "login":
        member = context['select_member']()
        if member:
            context['login'](member, headless=headless)
        return True
    if command == "dp-list":
        context['dp_list']()
        return True
    if command == "ipo":
        context['cmd_ipo']()
        return True
    if command == "nepse":
        context['cmd_nepse']()
        return True
    if command == "subidx":
        if positional_args:
            subindex_name = " ".join(positional_args)
        else:
            print("\nAvailable sub-indices: banking, development-bank, finance, hotels-and-tourism,")
            print("hydropower, investment, life-insurance, manufacturing-and-processing,")
            print("microfinance, non-life-insurance, others, trading")
            subindex_name = input("\nEnter sub-index name: ").strip()
        if subindex_name:
            context['cmd_subidx'](subindex_name)
        else:
            print("✗ Sub-index name is required.")
        return True
    if command == "mktsum":
        context['cmd_mktsum']()
        return True
    if command == "topgl":
        context['cmd_topgl']()
        return True
    if command == "stonk":
        symbol = positional_args[0] if positional_args else input("\nEnter stock symbol (e.g., NABIL): ").strip()
        if symbol:
            context['cmd_stonk'](symbol.upper())
        else:
            print("✗ Stock symbol is required.")
        return True
    if command == "dplist":
        context['dp_list']()
        return True
    if command in {"exit", "quit"}:
        return False
    return False


def main():
    """Modern interactive CLI entry point."""
    # Ensure Playwright browsers are available
    ensure_playwright_browsers()
    
    # All functions are now in this file - no imports needed from nepse_cli
    
    command_metadata = get_command_metadata()
    session = create_prompt_session(command_metadata)

    # Print logo BEFORE entering patch_stdout context so Rich colors work
    print_logo()
    print("\nType '/' to search commands, 'help' for hints, and 'exit' to quit.\n")

    context = {
        'apply_ipo': apply_ipo,
        'apply_all': apply_ipo_for_all_members,
        'add_member': add_family_member,
        'list_members': list_family_members,
        'edit_member': edit_family_member,
        'delete_member': delete_family_member,
        'manage_members': manage_family_members,
        'portfolio': get_portfolio_for_member,
        'login': test_login_for_member,
        'dp_list': get_dp_list,
        'cmd_ipo': cmd_ipo,
        'cmd_nepse': cmd_nepse,
        'cmd_subidx': cmd_subidx,
        'cmd_mktsum': cmd_mktsum,
        'cmd_topgl': cmd_topgl,
        'cmd_stonk': cmd_stonk,
        'select_member': select_family_member,
        'metadata': command_metadata,
        'category_order': COMMAND_CATEGORY_ORDER,
    }

    prompt_tokens = FormattedText([("class:prompt", "> ")])

    while True:
        try:
            with patch_stdout():
                user_input = session.prompt(prompt_tokens)
        except KeyboardInterrupt:
            print("\n(Press Ctrl+D or type 'exit' to quit, Enter to continue)")
            continue
        except EOFError:
            print("\nGoodbye!")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Handle "/command" syntax
        if user_input.startswith('/'):
            # Strip the slash
            user_input = user_input[1:].strip()
            
            # If user just typed '/' and hit enter, show palette (legacy behavior fallback)
            if not user_input:
                display_command_palette(command_metadata, COMMAND_CATEGORY_ORDER, "")
                continue

        try:
            tokens = shlex.split(user_input)
        except ValueError as exc:
            print(f"✗ Unable to parse input: {exc}")
            continue
        if not tokens:
            continue

        command = LEGACY_SHORTCUTS.get(tokens[0], tokens[0])
        args = tokens[1:]

        if command in {"exit", "quit"}:
            print("Goodbye!")
            break

        try:
            handled = execute_interactive_command(command, args, context)
            if not handled:
                print(f"Unknown command: '{user_input}'. Type '/' to explore commands.")
        except KeyboardInterrupt:
            print("\n\n✗ Command cancelled")
            continue
        except Exception as e:
            print(f"\n✗ Error executing command: {e}")
            continue

if __name__ == "__main__":
    main()
