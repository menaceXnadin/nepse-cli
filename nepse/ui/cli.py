"""
CLI Command handling and interactive shell.
"""

import sys
import shlex
import difflib
from typing import Dict, List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.patch_stdout import patch_stdout, StdoutProxy
from prompt_toolkit.formatted_text import FormattedText

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from ..config import CLI_HISTORY_FILE, ensure_history_file, get_member_by_name
from .console import CLI_PROMPT_STYLE, print_logo, console

# Command metadata
COMMAND_CATEGORY_ORDER = [
    "Market Data",
    "IPO Management",
    "Interactive Tools",
    "Configuration"
]


def get_command_metadata() -> List[Dict]:
    """Return metadata for all commands."""
    return [
        # Market Data
        {"name": "nepse", "description": "Display NEPSE indices", "category": "Market Data"},
        {"name": "subidx <name>", "description": "Show sub-index details", "category": "Market Data"},
        {"name": "mktsum", "description": "Display market summary", "category": "Market Data"},
        {"name": "topgl", "description": "Show top gainers and losers", "category": "Market Data"},
        {"name": "stonk <symbol>", "description": "Show stock details", "category": "Market Data"},
        {"name": "ipo", "description": "List open IPOs", "category": "IPO Management"},
        
        # IPO Management
        {"name": "apply", "description": "Apply for IPO (use --gui for browser)", "category": "IPO Management"},
        {"name": "apply-all", "description": "Apply IPO for all members", "category": "IPO Management"},
        
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


def fuzzy_filter_commands(commands: List[Dict], query: str) -> List[Dict]:
    """Filter commands using fuzzy matching."""
    if not query:
        return commands
    
    query_lower = query.lower()
    filtered = []
    
    for command in commands:
        haystack = f"{command['name']} {command['description']}".lower()
        if query_lower in haystack:
            filtered.append(command)
            continue
        ratio = difflib.SequenceMatcher(None, query_lower, command['name'].lower()).ratio()
        if ratio >= 0.6:
            filtered.append(command)
    
    return filtered


def display_command_palette(commands: List[Dict], category_order: List[str], query: str = "") -> None:
    """Display available commands in a categorized palette."""
    original_stdout = sys.stdout
    if isinstance(sys.stdout, StdoutProxy):
        sys.stdout = sys.stdout.original_stdout

    try:
        filtered_commands = fuzzy_filter_commands(commands, query)
        if not filtered_commands:
            message = f"No commands match '{query}'" if query else "No commands available"
            console.print(Panel(Text(message, justify="center"), title="Available Commands", border_style="red"))
            return

        grouped = {category: [] for category in category_order}
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
        sys.stdout = original_stdout


class NepseCommandCompleter(Completer):
    """Command completer for the NEPSE CLI."""
    
    def __init__(self, metadata: List[Dict]):
        self.metadata = metadata
        self.names = [m['name'] for m in metadata] + ["exit", "quit", "help", "?"]

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith('/'):
            query = text[1:].lower()
            for cmd in self.metadata:
                name = cmd['name']
                desc = cmd.get('description', '')
                if query in name.lower() or query in desc.lower():
                    yield Completion(
                        name,
                        start_position=-len(query),
                        display=FormattedText([
                            ("class:completion-command", f"{name:<15}"),
                            ("class:completion-description", f"  {desc}")
                        ]),
                    )
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
            word = text.split(' ')[-1]
            for name in self.names:
                if name.startswith(word):
                    yield Completion(name, start_position=-len(word))


LEGACY_SHORTCUTS = {
    "1": "apply", "2": "add", "3": "list", "4": "portfolio", "5": "login",
    "6": "dp-list", "7": "apply-all", "8": "ipo", "9": "nepse", "10": "subidx",
    "11": "mktsum", "12": "topgl", "13": "stonk", "0": "exit",
}


def create_prompt_session(command_metadata: List[Dict]) -> PromptSession:
    """Create a configured prompt session."""
    ensure_history_file()
    completer = NepseCommandCompleter(command_metadata)
    return PromptSession(
        history=FileHistory(str(CLI_HISTORY_FILE)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        complete_style=CompleteStyle.COLUMN,
        style=CLI_PROMPT_STYLE,
    )


def execute_interactive_command(command: str, args: List[str], context: Dict) -> bool:
    """
    Execute an interactive command.
    
    Args:
        command: Command name
        args: Command arguments
        context: Context dictionary with function references
        
    Returns:
        True if command was handled, False otherwise
    """
    command = command.lower()
    
    if command in {"help", "?"}:
        display_command_palette(context['metadata'], context['category_order'])
        return True

    flag_args = [arg for arg in args if arg.startswith("--")]
    positional_args = [arg for arg in args if not arg.startswith("--")]
    gui_requested = "--gui" in flag_args
    headless = not gui_requested

    if command == "apply":
        member_name = positional_args[0] if positional_args else None
        context['apply_ipo'](auto_load=True, headless=headless, member_name=member_name)
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
            member = get_member_by_name(positional_args[0])
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
    
    if command in {"dp-list", "dplist"}:
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
        if positional_args:
            # Join all positional arguments with spaces to support multiple stocks
            symbols = " ".join(positional_args)
        else:
            symbols = input("\nEnter stock symbol(s) (e.g., NABIL NICA SBL): ").strip()
        
        if symbols:
            context['cmd_stonk'](symbols.upper())
        else:
            print("✗ Stock symbol is required.")
        return True
    
    if command in {"exit", "quit"}:
        return False
    
    return False
