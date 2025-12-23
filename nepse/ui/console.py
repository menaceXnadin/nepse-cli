"""
Console styling and display utilities.
"""

from colorama import init as colorama_init
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import FormattedText

from rich.console import Console
from rich import box

# Initialize colorama
colorama_init(autoreset=True)

# Global console instance
console = Console(force_terminal=True, legacy_windows=False)

# CLI prompt styling
CLI_PROMPT_STYLE = PTStyle.from_dict({
    "prompt": "bold #4da6ff",
    "input": "#ffffff",
    
    # Completion Menu
    "completion-menu": "bg:#111111 noinherit",
    "completion-menu.completion": "bg:#111111 #bbbbbb",
    "completion-menu.completion.current": "bg:#2d2d2d #ffffff bold",
    
    # Custom classes
    "completion-command": "bold #ffffff",
    "completion-description": "italic #ff55ff",
    "completion-builtin": "italic #888888",
    
    "scrollbar.background": "bg:#111111",
    "scrollbar.button": "bg:#555555",
})


def print_logo() -> None:
    """Render the gradient welcome logo when interactive mode launches."""
    print("\n")
    logo_lines = [
        " ███╗   ██╗███████╗██████╗ ███████╗███████╗      ██████╗██╗     ██╗",
        " ████╗  ██║██╔════╝██╔══██╗██╔════╝██╔════╝     ██╔════╝██║     ██║",
        " ██╔██╗ ██║█████╗  ██████╔╝███████╗█████╗ █████╗██║     ██║     ██║",
        " ██║╚██╗██║██╔══╝  ██╔═══╝ ╚════██║██╔══╝ ╚════╝██║     ██║     ██║",
        " ██║ ╚████║███████╗██║     ███████║███████╗     ╚██████╗███████╗██║",
        " ╚═╝  ╚═══╝╚══════╝╚═╝     ╚══════╝╚══════╝      ╚═════╝╚══════╝╚═╝",
    ]
    colors = [(0, 255, 0), (0, 230, 0), (0, 204, 0), (0, 179, 0), (0, 153, 0), (0, 128, 0)]
    for idx, line in enumerate(logo_lines):
        r, g, b = colors[idx]
        print(f"\033[38;2;{r};{g};{b}m{line}\033[0m")
