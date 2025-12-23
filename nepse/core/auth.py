"""
Meroshare Authentication Module.
Handles all login operations with Playwright browser automation.
"""

import time
from typing import Dict, Optional, Tuple
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from ..ui.console import console


class MeroshareAuth:
    """
    Handles Meroshare authentication with reusable login logic.
    Eliminates duplicate login code across functions.
    """
    
    MEROSHARE_LOGIN_URL = "https://meroshare.cdsc.com.np/#/login"
    
    # Common selectors for form elements
    SELECTORS = {
        "dp_dropdown": "span.select2-selection",
        "dp_results": ".select2-results",
        "dp_search": "input.select2-search__field",
        "dp_option_highlighted": "li.select2-results__option--highlighted, li.select2-results__option[aria-selected='true']",
        "dp_options": "li.select2-results__option",
        "username": [
            "input[formcontrolname='username']",
            "input#username",
            "input[placeholder*='User']"
        ],
        "password": [
            "input[formcontrolname='password']",
            "input[type='password']"
        ],
        "login_button": [
            "button.btn.sign-in",
            "button[type='submit']",
            "button:has-text('Login')"
        ]
    }
    
    def __init__(self, headless: bool = True, slow_mo: int = 0):
        """
        Initialize authentication handler.
        
        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations by this many ms
        """
        self.headless = headless
        self.slow_mo = slow_mo if not headless else 0
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    def _fill_with_fallback(self, selectors: list, value: str, timeout: int = 2000) -> bool:
        """Try multiple selectors to fill a field."""
        for selector in selectors:
            try:
                self.page.fill(selector, value, timeout=timeout)
                return True
            except:
                continue
        return False
    
    def _click_with_fallback(self, selectors: list, timeout: int = 2000) -> bool:
        """Try multiple selectors to click an element."""
        for selector in selectors:
            try:
                self.page.click(selector, timeout=timeout)
                return True
            except:
                continue
        return False
    
    def _select_dp(self, dp_value: str) -> bool:
        """Select DP from dropdown."""
        try:
            # Click to open dropdown
            self.page.click(self.SELECTORS["dp_dropdown"])
            time.sleep(1)
            
            # Wait for results
            self.page.wait_for_selector(self.SELECTORS["dp_results"], timeout=5000)
            
            # Type in search box
            search_box = self.page.query_selector(self.SELECTORS["dp_search"])
            if search_box:
                search_box.type(dp_value)
                time.sleep(0.5)
                
                # Click highlighted result or press Enter
                first_result = self.page.query_selector(self.SELECTORS["dp_option_highlighted"])
                if first_result:
                    first_result.click()
                else:
                    self.page.keyboard.press("Enter")
            else:
                # Fallback: click by text
                results = self.page.query_selector_all(self.SELECTORS["dp_options"])
                for result in results:
                    if dp_value in result.inner_text():
                        result.click()
                        break
            
            time.sleep(1)
            return True
        except Exception as e:
            print(f"    ⚠ DP selection error: {e}")
            return False
    
    def login(self, member: Dict, show_progress: bool = True) -> Tuple[bool, Optional[Page]]:
        """
        Perform login for a member.
        
        Args:
            member: Dict with dp_value, username, password keys
            show_progress: Show progress bar during login
            
        Returns:
            Tuple of (success: bool, page: Page or None)
        """
        dp_value = member['dp_value']
        username = member['username']
        password = member['password']
        
        # Don't use 'with' - keep browser open for subsequent operations
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        
        try:
                if show_progress:
                    with console.status("[bold green]Logging in to Meroshare...", spinner="dots"):
                        self.page.goto(self.MEROSHARE_LOGIN_URL, wait_until="networkidle")
                        time.sleep(1)
                        
                        self.page.click(self.SELECTORS["dp_dropdown"])
                        time.sleep(1)
                        
                        self.page.wait_for_selector(self.SELECTORS["dp_results"], timeout=5000)
                        
                        search_box = self.page.query_selector(self.SELECTORS["dp_search"])
                        if search_box:
                            search_box.type(dp_value)
                            time.sleep(0.5)
                            
                            first_result = self.page.query_selector(self.SELECTORS["dp_option_highlighted"])
                            if first_result:
                                first_result.click()
                            else:
                                self.page.keyboard.press("Enter")
                        else:
                            results = self.page.query_selector_all(self.SELECTORS["dp_options"])
                            for result in results:
                                if dp_value in result.inner_text():
                                    result.click()
                                    break
                        
                        time.sleep(1)
                        
                        self._fill_with_fallback(self.SELECTORS["username"], username)
                        self._fill_with_fallback(self.SELECTORS["password"], password)
                        self._click_with_fallback(self.SELECTORS["login_button"])
                        
                        try:
                            self.page.wait_for_function(
                                "window.location.hash !== '#/login'", 
                                timeout=8000
                            )
                            time.sleep(2)
                        except:
                            time.sleep(2)
                else:
                    # No progress - silent mode
                    self.page.goto(self.MEROSHARE_LOGIN_URL, wait_until="networkidle")
                    time.sleep(1)
                    
                    if not self._select_dp(dp_value):
                        return False, None
                    
                    self._fill_with_fallback(self.SELECTORS["username"], username)
                    self._fill_with_fallback(self.SELECTORS["password"], password)
                    self._click_with_fallback(self.SELECTORS["login_button"])
                    
                    try:
                        self.page.wait_for_function(
                            "window.location.hash !== '#/login'", 
                            timeout=8000
                        )
                        time.sleep(2)
                    except:
                        time.sleep(2)
                
                time.sleep(2)
                
                # Check if login succeeded
                try:
                    self.page.wait_for_function(
                        "window.location.hash !== '#/login'", 
                        timeout=3000
                    )
                except:
                    pass
                
                current_url = self.page.url
                success = "#/login" not in current_url.lower()
                
                if show_progress and success:
                    console.print("[bold green]✓ Login successful[/bold green]\n")
                
                return success, self.page
                
        except Exception as e:
                if show_progress:
                    console.print(f"[red]✗ Login error: {e}[/red]")
                return False, None
    
    def login_with_context(self, member: Dict, context: BrowserContext) -> Tuple[bool, Optional[Page]]:
        """
        Perform login using an existing browser context (for multi-tab operations).
        
        Args:
            member: Dict with dp_value, username, password keys
            context: Existing browser context
            
        Returns:
            Tuple of (success: bool, page: Page or None)
        """
        dp_value = member['dp_value']
        username = member['username']
        password = member['password']
        
        self.page = context.new_page()
        
        try:
            self.page.goto(self.MEROSHARE_LOGIN_URL, wait_until="networkidle")
            time.sleep(2)
            
            if not self._select_dp(dp_value):
                return False, self.page
            
            self._fill_with_fallback(self.SELECTORS["username"], username)
            self._fill_with_fallback(self.SELECTORS["password"], password)
            self._click_with_fallback(self.SELECTORS["login_button"])
            
            try:
                self.page.wait_for_function(
                    "window.location.hash !== '#/login'", 
                    timeout=8000
                )
                time.sleep(2)
            except:
                time.sleep(2)
            
            success = "#/login" not in self.page.url.lower()
            return success, self.page
            
        except Exception as e:
            print(f"✗ Login error: {e}")
            return False, self.page
    
    def close(self) -> None:
        """Close browser and cleanup."""
        if self.browser:
            self.browser.close()
            self.browser = None
            self.context = None
            self.page = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None


def test_login_for_member(member: Dict, headless: bool = True) -> bool:
    """
    Test login for a specific family member.
    
    Args:
        member: Member dictionary with credentials
        headless: Run browser in headless mode
        
    Returns:
        True if login successful, False otherwise
    """
    console.print(f"\n[bold cyan]Testing login for:[/bold cyan] [bold white]{member['name']}[/bold white]...\n")
    
    auth = MeroshareAuth(headless=headless, slow_mo=100)
    success, page = auth.login(member, show_progress=True)
    
    if success:
        console.print(f"[bold green]✓✓✓ LOGIN SUCCESSFUL for {member['name']}! ✓✓✓[/bold green]\n")
    else:
        console.print(f"[yellow]⚠ Login may have failed for {member['name']}[/yellow]\n")
    
    if not headless and page:
        console.print("[dim]Browser will stay open for 20 seconds...[/dim]")
        time.sleep(20)
    
    auth.close()
    return success
