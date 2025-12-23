"""
NEPSE CLI - Stock Market & IPO Automation Tool

A command-line tool for:
- Viewing NEPSE market data (indices, stocks, IPOs)
- Automating Meroshare IPO applications
- Managing family member credentials
- Portfolio tracking

Usage:
    python main.py   # Start interactive CLI
    nepse            # If installed via pip

Author: NEPSE CLI Team
"""

import shlex
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import FormattedText

# Import utilities
from nepse.utils.browser import ensure_playwright_browsers

# Import core functionality
from nepse.core.auth import test_login_for_member
from nepse.core.portfolio import get_portfolio_for_member
from nepse.core.ipo import apply_ipo, apply_ipo_for_all_members

# Import services
from nepse.services.market import (
    cmd_ipo,
    cmd_nepse,
    cmd_subidx,
    cmd_mktsum,
    cmd_topgl,
    cmd_stonk,
    get_dp_list
)

# Import UI components
from nepse.ui.console import print_logo
from nepse.ui.member_ui import (
    add_family_member,
    list_family_members,
    edit_family_member,
    delete_family_member,
    manage_family_members,
    select_family_member
)
from nepse.ui.cli import (
    get_command_metadata,
    create_prompt_session,
    execute_interactive_command,
    display_command_palette,
    COMMAND_CATEGORY_ORDER,
    LEGACY_SHORTCUTS
)


def main():
    """Main entry point for the NEPSE CLI."""
    # Ensure Playwright browsers are available
    ensure_playwright_browsers()
    
    # Get command metadata and create session
    command_metadata = get_command_metadata()
    session = create_prompt_session(command_metadata)

    # Print logo before entering patch_stdout context
    print_logo()
    print("\nType '/' to search commands, 'help' for hints, and 'exit' to quit.\n")

    # Build execution context with all function references
    context = {
        # IPO functions
        'apply_ipo': apply_ipo,
        'apply_all': apply_ipo_for_all_members,
        
        # Member management
        'add_member': add_family_member,
        'list_members': list_family_members,
        'edit_member': edit_family_member,
        'delete_member': delete_family_member,
        'manage_members': manage_family_members,
        'select_member': select_family_member,
        
        # Core operations
        'portfolio': get_portfolio_for_member,
        'login': test_login_for_member,
        
        # Market data
        'dp_list': get_dp_list,
        'cmd_ipo': cmd_ipo,
        'cmd_nepse': cmd_nepse,
        'cmd_subidx': cmd_subidx,
        'cmd_mktsum': cmd_mktsum,
        'cmd_topgl': cmd_topgl,
        'cmd_stonk': cmd_stonk,
        
        # Metadata
        'metadata': command_metadata,
        'category_order': COMMAND_CATEGORY_ORDER,
    }

    prompt_tokens = FormattedText([("class:prompt", "> ")])

    # Main REPL loop
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
            user_input = user_input[1:].strip()
            
            # Show palette if just '/'
            if not user_input:
                display_command_palette(command_metadata, COMMAND_CATEGORY_ORDER, "")
                continue

        # Parse command
        try:
            tokens = shlex.split(user_input)
        except ValueError as exc:
            print(f"✗ Unable to parse input: {exc}")
            continue
        
        if not tokens:
            continue

        # Resolve legacy shortcuts
        command = LEGACY_SHORTCUTS.get(tokens[0], tokens[0])
        args = tokens[1:]

        # Handle exit
        if command in {"exit", "quit"}:
            print("Goodbye!")
            break

        # Execute command
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
