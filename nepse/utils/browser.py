"""
Browser utility functions for Playwright.
"""

import sys
import subprocess


def ensure_playwright_browsers() -> None:
    """Ensure Playwright browsers are installed, install if missing."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, timeout=5000)
            browser.close()
    except Exception:
        print("[yellow]⚠️  Playwright browsers not found. Installing chromium...[/yellow]")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                print("[green]✓ Browsers installed successfully![/green]")
            else:
                print(f"[red]✗ Failed to install browsers: {result.stderr}[/red]")
                print("[yellow]You can install manually with: playwright install chromium[/yellow]")
        except subprocess.TimeoutExpired:
            print("[red]✗ Browser installation timed out. Please install manually.[/red]")
        except Exception as e:
            print(f"[red]✗ Error installing browsers: {e}[/red]")
