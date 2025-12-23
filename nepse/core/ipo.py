"""
IPO Application Module.
Handles IPO listing, application, and batch processing.
"""

import time
from typing import Dict, List, Optional, Tuple
from playwright.sync_api import sync_playwright, Page, BrowserContext

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich import box

from .auth import MeroshareAuth
from ..config import DATA_DIR

console = Console(force_terminal=True, legacy_windows=False)


class IPOManager:
    """Handles IPO browsing and application operations."""
    
    ASBA_URL = "https://meroshare.cdsc.com.np/#/asba"
    
    def __init__(self, page: Page):
        """
        Initialize with an authenticated page.
        
        Args:
            page: Authenticated Playwright page
        """
        self.page = page
    
    def fetch_available_ipos(self) -> List[Dict]:
        """
        Fetch available IPOs from Meroshare.
        
        Returns:
            List of available IPO dictionaries
        """
        try:
            self.page.goto(self.ASBA_URL, wait_until="networkidle")
            time.sleep(3)
            
            try:
                self.page.wait_for_selector(".company-list", timeout=10000)
                time.sleep(2)
            except:
                pass
            
            company_rows = self.page.query_selector_all(".company-list")
            if not company_rows:
                return []
            
            available_ipos = []
            for row in company_rows:
                try:
                    company_name_elem = row.query_selector(".company-name span")
                    share_type_elem = row.query_selector(".share-of-type")
                    share_group_elem = row.query_selector(".isin")
                    
                    if company_name_elem and share_type_elem and share_group_elem:
                        company_name = company_name_elem.inner_text().strip()
                        share_type = share_type_elem.inner_text().strip()
                        share_group = share_group_elem.inner_text().strip()
                        
                        if "ipo" in share_type.lower() and "ordinary" in share_group.lower():
                            apply_button = row.query_selector("button.btn-issue")
                            
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
                except Exception:
                    continue
            
            return available_ipos
            
        except Exception as e:
            console.print(f"[red]Error fetching IPOs: {e}[/red]")
            return []
    
    def apply_for_ipo(
        self, 
        ipo: Dict, 
        member: Dict
    ) -> Tuple[bool, str]:
        """
        Apply for a specific IPO.
        
        Args:
            ipo: IPO dictionary with apply_button
            member: Member dictionary with credentials
            
        Returns:
            Tuple of (success, status_message)
        """
        try:
            # Check if already applied
            if ipo.get('is_applied', False):
                return True, "already_applied"
            
            # Click Apply button
            ipo['apply_button'].click()
            time.sleep(3)
            
            # Fill form
            self.page.wait_for_selector("select#selectBank", timeout=10000)
            time.sleep(2)
            
            # Get minimum quantity from the form
            try:
                labels = self.page.query_selector_all("label")
                min_quantity = member['applied_kitta']  # Default to member's setting
                
                for label in labels:
                    if "Minimum Quantity" in label.inner_text():
                        # Find the sibling form-value div
                        parent = label.evaluate_handle("el => el.closest('.form-group')")
                        form_value = parent.as_element().query_selector(".form-value span")
                        if form_value:
                            form_min_qty = int(form_value.inner_text().strip())
                            # Use the maximum of form minimum and member's default
                            min_quantity = max(min_quantity, form_min_qty)
                            if form_min_qty > member['applied_kitta']:
                                console.print(f"[yellow]⚠ Adjusting quantity from {member['applied_kitta']} to minimum {form_min_qty}[/yellow]")
                            break
            except Exception as e:
                console.print(f"[dim]Could not read minimum quantity, using default: {e}[/dim]")
                min_quantity = member['applied_kitta']
            
            # Select bank
            bank_options = self.page.query_selector_all("select#selectBank option")
            valid_banks = [opt for opt in bank_options if opt.get_attribute("value")]
            if valid_banks:
                self.page.select_option("select#selectBank", valid_banks[0].get_attribute("value"))
            else:
                return False, "No banks found"
            time.sleep(2)
            
            # Select account
            self.page.wait_for_selector("select#accountNumber", timeout=5000)
            account_options = self.page.query_selector_all("select#accountNumber option")
            valid_accounts = [opt for opt in account_options if opt.get_attribute("value")]
            if valid_accounts:
                self.page.select_option("select#accountNumber", valid_accounts[0].get_attribute("value"))
            else:
                return False, "No accounts found"
            time.sleep(2)
            
            # Fill kitta with adjusted quantity
            self.page.fill("input#appliedKitta", str(min_quantity))
            time.sleep(1)
            self.page.fill("input#crnNumber", member['crn_number'])
            time.sleep(1)
            
            # Accept disclaimer
            disclaimer = self.page.query_selector("input#disclaimer")
            if disclaimer:
                disclaimer.check()
            time.sleep(1)
            
            # Click proceed
            proceed_button = self.page.query_selector("button.btn-primary[type='submit']")
            if proceed_button:
                proceed_button.click()
            else:
                return False, "Proceed button not found"
            time.sleep(3)
            
            # Enter PIN
            self.page.wait_for_selector("input#transactionPIN", timeout=10000)
            time.sleep(2)
            self.page.fill("input#transactionPIN", member['transaction_pin'])
            time.sleep(2)
            
            # Submit application
            clicked = self._click_submit_button()
            if not clicked:
                return False, "Failed to click submit button"
            
            time.sleep(5)
            return True, "success"
            
        except Exception as e:
            return False, str(e)
    
    def _click_submit_button(self) -> bool:
        """Try multiple methods to click the Apply/Submit button."""
        # Method 1: Find button with text "Apply"
        try:
            apply_buttons = self.page.query_selector_all("button:has-text('Apply')")
            for btn in apply_buttons:
                if btn.is_visible() and not btn.is_disabled():
                    btn.click()
                    return True
        except:
            pass
        
        # Method 2: Find by class in confirm page
        try:
            submit_button = self.page.query_selector("div.confirm-page-btn button.btn-primary[type='submit']")
            if submit_button and submit_button.is_visible():
                submit_button.click()
                return True
        except:
            pass
        
        # Method 3: Alternative submit button
        try:
            submit_button = self.page.query_selector("button.btn-gap.btn-primary[type='submit']")
            if submit_button and submit_button.is_visible():
                submit_button.click()
                return True
        except:
            pass
        
        # Method 4: JavaScript fallback
        try:
            self.page.evaluate("""
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.includes('Apply') && btn.type === 'submit') {
                        btn.click();
                        break;
                    }
                }
            """)
            return True
        except:
            pass
        
        return False


def display_ipo_table(ipos: List[Dict]) -> None:
    """Display available IPOs in a table."""
    table = Table(
        title="Available IPOs (Ordinary Shares)", 
        box=box.ROUNDED,
        header_style="bold cyan"
    )
    table.add_column("No.", justify="right", style="cyan")
    table.add_column("Company", style="bold white")
    table.add_column("Type", style="yellow")
    table.add_column("Group", style="dim")
    table.add_column("Status", justify="center")
    
    for ipo in ipos:
        status = "[yellow]Applied[/yellow]" if ipo.get('is_applied') else "[green]Available[/green]"
        table.add_row(
            str(ipo['index']),
            ipo['company_name'],
            ipo['share_type'],
            ipo['share_group'],
            status
        )
    
    console.print(table)


def apply_ipo(
    auto_load: bool = True, 
    headless: bool = False, 
    member_name: Optional[str] = None
) -> None:
    """
    Apply for IPO with selected member.
    
    Args:
        auto_load: Load credentials from config
        headless: Run browser in headless mode
        member_name: Optional specific member name
    """
    from ..config import get_member_by_name
    from ..ui.member_ui import select_family_member
    
    member = None
    if member_name:
        member = get_member_by_name(member_name)
        if not member:
            console.print(f"\n[red]✗ Member '{member_name}' not found.[/red]")
            return
    
    if not member:
        member = select_family_member()
    
    if not member:
        console.print("\n[red]✗ No member selected. Exiting...[/red]")
        return
    
    if not member.get('crn_number'):
        console.print("[red]✗ CRN number is required![/red]")
        return
    
    console.print(f"\n[bold green]✓ Applying IPO for:[/bold green] {member['name']}")
    console.print(f"[bold green]✓ Kitta:[/bold green] {member['applied_kitta']} [bold green]| CRN:[/bold green] {member['crn_number']}")
    
    auth = MeroshareAuth(headless=headless, slow_mo=100)
    success, page = auth.login(member, show_progress=True)
    
    if not success or not page:
        console.print("[red]✗ Login failed[/red]")
        auth.close()
        return
    
    console.print("[bold green]✓ Login successful[/bold green]\n")
    
    # Fetch IPOs
    with console.status("[bold green]Fetching available IPOs...", spinner="dots"):
        ipo_manager = IPOManager(page)
        available_ipos = ipo_manager.fetch_available_ipos()
    
    if not available_ipos:
        console.print("[bold yellow]⚠ No IPOs available[/bold yellow]")
        if not headless:
            time.sleep(20)
        auth.close()
        return
    
    console.print("[bold green]✓ IPOs fetched successfully[/bold green]\n")
    display_ipo_table(available_ipos)
    
    # Auto-select first IPO for both headless and GUI mode
    selected_idx = 0
    console.print(f"\n→ Auto-selecting IPO #1: {available_ipos[0]['company_name']}")
    
    selected_ipo = available_ipos[selected_idx]
    console.print(f"\n[bold green]✓ Selected:[/bold green] {selected_ipo['company_name']}\n")
    
    # Apply
    with console.status("[bold green]Applying for IPO...", spinner="dots"):
        success, status = ipo_manager.apply_for_ipo(selected_ipo, member)
    
    if success:
        if status == "already_applied":
            console.print("[yellow]⚠ IPO already applied for this account[/yellow]")
        else:
            console.print("\n[bold green]✓✓✓ APPLICATION SUBMITTED! ✓✓✓[/bold green]")
    else:
        console.print(f"[red]✗ Application failed: {status}[/red]")
    
    if not headless:
        console.print("\n[dim]Browser will stay open for 30 seconds...[/dim]")
        time.sleep(30)
    
    auth.close()


def apply_ipo_for_all_members(headless: bool = True) -> None:
    """
    Apply IPO for multiple family members using multi-tab browser.
    
    Args:
        headless: Run browser in headless mode
    """
    from ..config import get_all_members
    from ..ui.member_ui import select_members_for_ipo
    
    all_members = get_all_members()
    
    if not all_members:
        console.print(Panel(
            "[bold red]⚠ No family members found. Add members first![/bold red]",
            box=box.ROUNDED, 
            border_style="red"
        ))
        return
    
    # Interactive selection
    console.print()
    members = select_members_for_ipo(all_members)
    
    if not members:
        return
    
    # Show selected members
    console.print()
    table = Table(
        title="✓ Selected Members for IPO Application",
        box=box.ROUNDED,
        header_style="bold green",
        border_style="green"
    )
    table.add_column("No.", justify="right", style="cyan")
    table.add_column("Name", style="bold white")
    table.add_column("Kitta", justify="right", style="yellow")
    table.add_column("CRN", style="dim")
    
    for idx, member in enumerate(members, 1):
        table.add_row(
            str(idx),
            member['name'],
            str(member['applied_kitta']),
            member['crn_number']
        )
    
    console.print(table)
    console.print()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context()
        
        try:
            # Phase 1: Login all members
            console.print()
            console.print(Rule("[bold cyan]PHASE 1: MULTI-TAB LOGIN[/bold cyan]"))
            console.print()
            
            pages_data = []
            auth = MeroshareAuth(headless=headless)
            
            for idx, member in enumerate(members, 1):
                member_name = member['name']
                console.print(f"[cyan][Tab {idx}][/cyan] Logging in: [bold]{member_name}[/bold]")
                
                with console.status(f"[bold green][Tab {idx}] Logging in...", spinner="dots"):
                    success, page = auth.login_with_context(member, context)
                
                if success:
                    console.print(f"[green]✓ [Tab {idx}] Login successful: {member_name}[/green]")
                    pages_data.append({
                        "success": True,
                        "member": member,
                        "page": page,
                        "tab_index": idx
                    })
                else:
                    console.print(f"[red]✗ [Tab {idx}] Login failed: {member_name}[/red]")
                    pages_data.append({
                        "success": False,
                        "member": member,
                        "page": page,
                        "tab_index": idx,
                        "error": "Login failed"
                    })
            
            successful_logins = [p for p in pages_data if p['success']]
            
            if not successful_logins:
                console.print("[bold red]\n✗ No successful logins. Exiting...[/bold red]")
                return
            
            # Phase 2: Apply IPO
            console.print()
            console.print(Rule("[bold cyan]PHASE 2: IPO APPLICATION[/bold cyan]"))
            console.print()
            
            # Fetch IPOs from first successful login
            first_page = successful_logins[0]['page']
            ipo_manager = IPOManager(first_page)
            
            with console.status("[bold green]Fetching available IPOs...", spinner="dots"):
                available_ipos = ipo_manager.fetch_available_ipos()
            
            if not available_ipos:
                console.print("[bold yellow]⚠ No IPOs available[/bold yellow]")
                return
            
            console.print("[bold green]✓ IPOs fetched successfully[/bold green]\n")
            display_ipo_table(available_ipos)
            
            # Select IPO
            if not headless:
                selection = input(f"\nSelect IPO (1-{len(available_ipos)}): ").strip()
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
            console.print(Panel(
                f"[bold green]✓ Selected IPO: {selected_ipo['company_name']}[/bold green]\n"
                f"[yellow]⚠ Will apply for {len(successful_logins)} member(s)[/yellow]",
                box=box.ROUNDED
            ))
            
            # Apply for each member
            application_results = []
            
            for page_data in successful_logins:
                member = page_data['member']
                page = page_data['page']
                tab_index = page_data['tab_index']
                
                console.print()
                console.print(Rule(f"[Tab {tab_index}] APPLYING FOR: {member['name']}"))
                
                try:
                    with console.status(f"[bold green][Tab {tab_index}] Navigating...", spinner="dots"):
                        page.goto("https://meroshare.cdsc.com.np/#/asba", wait_until="networkidle")
                        time.sleep(3)
                        page.wait_for_selector(".company-list", timeout=10000)
                        time.sleep(2)
                    
                    # Find and click IPO
                    company_rows = page.query_selector_all(".company-list")
                    ipo_found = False
                    already_applied = False
                    
                    for row in company_rows:
                        try:
                            company_name_elem = row.query_selector(".company-name span")
                            if company_name_elem and selected_ipo['company_name'] in company_name_elem.inner_text():
                                apply_button = row.query_selector("button.btn-issue")
                                if apply_button:
                                    button_text = apply_button.inner_text().strip().lower()
                                    
                                    if "edit" in button_text or "view" in button_text:
                                        already_applied = True
                                        ipo_found = True
                                        break
                                    else:
                                        apply_button.click()
                                        ipo_found = True
                                        break
                        except:
                            continue
                    
                    if already_applied:
                        console.print(f"[green]✓ [Tab {tab_index}] Skipping - already applied[/green]")
                        application_results.append({
                            "member": member['name'],
                            "success": True,
                            "status": "already_applied"
                        })
                        continue
                    
                    if not ipo_found:
                        raise Exception("IPO not found")
                    
                    time.sleep(3)
                    
                    # Fill form
                    with console.status(f"[bold green][Tab {tab_index}] Filling form...", spinner="dots"):
                        page.wait_for_selector("select#selectBank", timeout=10000)
                        time.sleep(2)
                        
                        # Get minimum quantity from the form
                        try:
                            labels = page.query_selector_all("label")
                            min_quantity = member['applied_kitta']  # Default to member's setting
                            
                            for label in labels:
                                if "Minimum Quantity" in label.inner_text():
                                    # Find the sibling form-value div
                                    parent = label.evaluate_handle("el => el.closest('.form-group')")
                                    form_value = parent.as_element().query_selector(".form-value span")
                                    if form_value:
                                        form_min_qty = int(form_value.inner_text().strip())
                                        # Use the maximum of form minimum and member's default
                                        min_quantity = max(min_quantity, form_min_qty)
                                        if form_min_qty > member['applied_kitta']:
                                            console.print(f"[yellow][Tab {tab_index}] Adjusting quantity from {member['applied_kitta']} to minimum {form_min_qty}[/yellow]")
                                        break
                        except Exception:
                            min_quantity = member['applied_kitta']
                        
                        bank_options = page.query_selector_all("select#selectBank option")
                        valid_banks = [opt for opt in bank_options if opt.get_attribute("value")]
                        if valid_banks:
                            page.select_option("select#selectBank", valid_banks[0].get_attribute("value"))
                        time.sleep(2)
                        
                        page.wait_for_selector("select#accountNumber", timeout=5000)
                        account_options = page.query_selector_all("select#accountNumber option")
                        valid_accounts = [opt for opt in account_options if opt.get_attribute("value")]
                        if valid_accounts:
                            page.select_option("select#accountNumber", valid_accounts[0].get_attribute("value"))
                        time.sleep(2)
                        
                        page.fill("input#appliedKitta", str(min_quantity))
                        time.sleep(1)
                        page.fill("input#crnNumber", member['crn_number'])
                        time.sleep(1)
                        
                        disclaimer = page.query_selector("input#disclaimer")
                        if disclaimer:
                            disclaimer.check()
                        time.sleep(1)
                        
                        proceed = page.query_selector("button.btn-primary[type='submit']")
                        if proceed:
                            proceed.click()
                        time.sleep(3)
                    
                    # Enter PIN and submit
                    with console.status(f"[bold green][Tab {tab_index}] Submitting...", spinner="dots"):
                        page.wait_for_selector("input#transactionPIN", timeout=10000)
                        time.sleep(2)
                        page.fill("input#transactionPIN", member['transaction_pin'])
                        time.sleep(2)
                        
                        # Click submit
                        try:
                            apply_buttons = page.query_selector_all("button:has-text('Apply')")
                            for btn in apply_buttons:
                                if btn.is_visible() and not btn.is_disabled():
                                    btn.click()
                                    break
                        except:
                            page.evaluate("""
                                const buttons = document.querySelectorAll('button');
                                for (const btn of buttons) {
                                    if (btn.textContent.includes('Apply') && btn.type === 'submit') {
                                        btn.click();
                                        break;
                                    }
                                }
                            """)
                        
                        time.sleep(5)
                    
                    console.print(f"[bold green]✓ [Tab {tab_index}] Application submitted for {member['name']}![/bold green]")
                    application_results.append({
                        "member": member['name'],
                        "success": True
                    })
                    
                except Exception as e:
                    console.print(f"[bold red]✗ [Tab {tab_index}] Failed: {e}[/bold red]")
                    application_results.append({
                        "member": member['name'],
                        "success": False,
                        "error": str(e)
                    })
                    page.screenshot(path=str(DATA_DIR / f"error_{member['name']}.png"))
            
            # Final summary
            console.print()
            successful = [r for r in application_results if r['success']]
            failed = [r for r in application_results if not r['success']]
            
            summary_table = Table(
                title=f"Final Summary: {selected_ipo['company_name']}",
                box=box.ROUNDED
            )
            summary_table.add_column("Member", style="white")
            summary_table.add_column("Status", style="bold")
            summary_table.add_column("Details", style="dim")
            
            for r in successful:
                status = "[yellow]Already Applied[/yellow]" if r.get('status') == 'already_applied' else "[green]Success[/green]"
                details = "Skipped" if r.get('status') == 'already_applied' else "Applied"
                summary_table.add_row(r['member'], status, details)
            
            for r in failed:
                summary_table.add_row(r['member'], "[red]Failed[/red]", r.get('error', 'Unknown'))
            
            console.print(summary_table)
            
            if not headless:
                console.print("\n[dim]Browser will stay open for 60 seconds...[/dim]")
                time.sleep(60)
            
        except Exception as e:
            console.print(f"\n[bold red]✗ Critical error: {e}[/bold red]")
        finally:
            browser.close()
