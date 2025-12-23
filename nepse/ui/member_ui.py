"""
Member management UI components.
Family member CRUD operations with Rich UI.
"""

from typing import Dict, List, Optional, Tuple

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import FormattedText

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box

from ..config import (
    load_family_members, 
    save_family_members,
    get_all_members,
    add_member as config_add_member,
    delete_member as config_delete_member
)

console = Console(force_terminal=True, legacy_windows=False)


def select_member_interactive(
    title: str = "Select Family Member", 
    show_details: bool = True
) -> Tuple[Optional[Dict], Optional[int]]:
    """
    Generic interactive member selector with arrow keys.
    
    Args:
        title: Title for the selection menu
        show_details: Whether to show member details after selection
        
    Returns:
        Tuple of (selected_member, index) or (None, None) if cancelled
    """
    members = get_all_members()
    
    if not members:
        console.print(Panel(
            "⚠ No family members found. Add members first!",
            style="bold red",
            box=box.ROUNDED
        ))
        return None, None
    
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
                result.append(('class:selected', f' > {member["name"]} (DP: {member["dp_value"]})\n'))
            else:
                result.append(('class:unselected', f'   {member["name"]} (DP: {member["dp_value"]})\n'))
        return FormattedText(result)

    style = PTStyle.from_dict({
        'selected': 'fg:ansigreen bold',
        'unselected': '',
        'title': 'bold underline'
    })

    app = Application(
        layout=Layout(
            Window(content=FormattedTextControl(get_formatted_text), height=len(members) + 2)
        ),
        key_bindings=bindings,
        style=style,
        full_screen=False,
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


def select_family_member() -> Optional[Dict]:
    """Select a family member for IPO application."""
    selected, _ = select_member_interactive("Select Family Member", show_details=True)
    return selected


def select_members_for_ipo(members: List[Dict]) -> List[Dict]:
    """
    Interactive checkbox-style selection for IPO application.
    
    Controls:
    - ↑/↓: Navigate
    - Space: Toggle selection
    - A: Select/Deselect all
    - Enter: Confirm
    - Ctrl+C: Cancel
    
    Returns:
        List of selected members
    """
    if not members:
        return []
    
    selected = [True] * len(members)
    current_index = 0
    
    bindings = KeyBindings()
    
    @bindings.add('up')
    def _(event):
        nonlocal current_index
        current_index = (current_index - 1) % len(members)
    
    @bindings.add('down')
    def _(event):
        nonlocal current_index
        current_index = (current_index + 1) % len(members)
    
    @bindings.add('space')
    def _(event):
        nonlocal selected
        selected[current_index] = not selected[current_index]
    
    @bindings.add('a')
    def _(event):
        nonlocal selected
        if all(selected):
            selected = [False] * len(members)
        else:
            selected = [True] * len(members)
    
    @bindings.add('enter')
    def _(event):
        event.app.exit(result=selected)
    
    @bindings.add('c-c')
    def _(event):
        event.app.exit(result=None)
    
    def get_formatted_text():
        result = []
        result.append(('class:title', '╔════════════════════════════════════════════════════════════════════╗\n'))
        result.append(('class:title', '║  Select Members for IPO Application                                ║\n'))
        result.append(('class:title', '╚════════════════════════════════════════════════════════════════════╝\n'))
        result.append(('class:help', '  Controls: [↑/↓] Navigate | [Space] Toggle | [A] All/None | [Enter] Confirm\n\n'))
        
        for i, member in enumerate(members):
            checkbox = '[X]' if selected[i] else '[ ]'
            member_info = f"{member['name']:<15} | Kitta: {member['applied_kitta']:<4} | CRN: {member['crn_number']}"
            
            if i == current_index:
                if selected[i]:
                    result.append(('class:selected-checked', f'  > {checkbox}  {member_info}\n'))
                else:
                    result.append(('class:selected-unchecked', f'  > {checkbox}  {member_info}\n'))
            else:
                if selected[i]:
                    result.append(('class:checked', f'    {checkbox}  {member_info}\n'))
                else:
                    result.append(('class:unchecked', f'    {checkbox}  {member_info}\n'))
        
        selected_count = sum(selected)
        result.append(('class:separator', '\n  ──────────────────────────────────────────────────────────\n'))
        result.append(('class:footer', f'  Selected: {selected_count}/{len(members)} members'))
        
        return FormattedText(result)
    
    style = PTStyle.from_dict({
        'title': 'bold cyan',
        'help': 'italic #888888',
        'selected-checked': 'bg:#00aa00 #ffffff bold',
        'selected-unchecked': 'bg:#aa5500 #ffffff bold',
        'checked': 'bold #00ff00',
        'unchecked': '#555555',
        'separator': '#333333',
        'footer': 'bold cyan',
    })
    
    app = Application(
        layout=Layout(
            Window(content=FormattedTextControl(get_formatted_text), height=len(members) + 6)
        ),
        key_bindings=bindings,
        style=style,
        full_screen=False,
        mouse_support=False
    )
    
    try:
        result = app.run()
        
        if result is None:
            console.print("\n[yellow]✗ Selection cancelled[/yellow]")
            return []
        
        selected_members = [member for i, member in enumerate(members) if result[i]]
        
        if not selected_members:
            console.print("\n[yellow]⚠ No members selected[/yellow]")
            return []
        
        console.print(f"\n[bold green]✓ Selected {len(selected_members)} member(s)[/bold green]")
        return selected_members
        
    except Exception as e:
        console.print(f"[yellow]Interactive menu failed ({str(e)}). Please try again.[/yellow]")
        return []


def add_family_member() -> None:
    """Add a new family member with enhanced UI."""
    console.print("\n")
    console.print(Panel(
        "[bold cyan]Add New Family Member[/bold cyan]",
        border_style="cyan",
        box=box.DOUBLE,
        expand=False,
        padding=(0, 2)
    ))
    
    config = load_family_members()
    
    # Member Name
    console.print("\n[bold yellow]📝 Member Information[/bold yellow]")
    member_name = Prompt.ask("[cyan]Member name[/cyan] (e.g., Dad, Mom, Me)").strip()
    
    if not member_name:
        console.print("[red]✗ Member name cannot be empty![/red]")
        return
    
    # Check if exists
    for member in config.get('members', []):
        if member['name'].lower() == member_name.lower():
            console.print(f"\n[yellow]⚠ Member '{member_name}' already exists![/yellow]")
            update = Prompt.ask("[cyan]Update this member?[/cyan]", choices=["yes", "no"], default="no")
            if update != 'yes':
                console.print("[yellow]✗ Cancelled[/yellow]")
                return
            config['members'].remove(member)
            break
    
    # Credentials
    console.print("\n[bold yellow]🔐 Meroshare Credentials[/bold yellow]")
    
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
    
    console.print("\n")
    console.print(Panel(
        f"[bold green]✓ Member '{member_name}' added successfully![/bold green]\n"
        f"[white]Total members: {len(config['members'])}[/white]",
        border_style="green",
        box=box.DOUBLE,
        expand=False,
        padding=(0, 2)
    ))
    console.print("")


def list_family_members() -> Optional[List[Dict]]:
    """List all family members with enhanced UI."""
    members = get_all_members()
    
    if not members:
        console.print(Panel(
            "[bold red]⚠ No family members found.[/bold red]\n"
            "[yellow]Use 'add' command to add members first![/yellow]",
            box=box.ROUNDED,
            border_style="red"
        ))
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


def edit_family_member() -> None:
    """Edit an existing family member."""
    config = load_family_members()
    members = config.get('members', [])
    
    if not members:
        console.print(Panel(
            "[bold red]⚠ No family members found.[/bold red]",
            box=box.ROUNDED,
            border_style="red"
        ))
        return
    
    console.print("\n")
    console.print(Panel(
        "[bold cyan]Edit Family Member[/bold cyan]",
        border_style="cyan",
        box=box.DOUBLE,
        expand=False,
        padding=(0, 2)
    ))
    
    member, index = select_member_interactive("Select member to edit", show_details=False)
    
    if not member:
        return
    
    try:
        console.print("\n")
        console.print(Panel(
            f"[bold cyan]Edit Member: {member['name']}[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE,
            expand=False,
            padding=(0, 2)
        ))
        
        console.print("\n[dim]Press Enter to keep current value[/dim]\n")
        
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
        console.print(Panel(
            f"[bold green]✓ Member '{new_name}' updated successfully![/bold green]",
            border_style="green",
            box=box.DOUBLE,
            expand=False,
            padding=(0, 2)
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Edit cancelled[/yellow]")


def delete_family_member() -> None:
    """Delete a family member."""
    config = load_family_members()
    members = config.get('members', [])
    
    if not members:
        console.print(Panel(
            "[bold red]⚠ No family members found.[/bold red]",
            box=box.ROUNDED,
            border_style="red"
        ))
        return
    
    console.print("\n")
    console.print(Panel(
        "[bold red]Delete Family Member[/bold red]",
        border_style="red",
        box=box.DOUBLE,
        expand=False,
        padding=(0, 2)
    ))
    
    member, index = select_member_interactive("Select member to delete", show_details=False)
    
    if not member:
        return
    
    try:
        console.print("\n")
        console.print(Panel(
            f"[bold red]Delete Member: {member['name']}[/bold red]\n\n"
            f"[yellow]⚠ This action cannot be undone![/yellow]",
            border_style="red",
            box=box.DOUBLE,
            expand=False,
            padding=(0, 2)
        ))
        
        confirm = Prompt.ask("\n[red]Type the member name to confirm deletion[/red]").strip()
        
        if confirm.lower() != member['name'].lower():
            console.print("[yellow]✗ Deletion cancelled - name didn't match[/yellow]")
            return
        
        config_delete_member(index)
        
        console.print("\n")
        console.print(Panel(
            f"[bold green]✓ Member '{member['name']}' deleted successfully![/bold green]",
            border_style="green",
            box=box.DOUBLE,
            expand=False,
            padding=(0, 2)
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Deletion cancelled[/yellow]")


def manage_family_members() -> None:
    """Interactive family member management menu."""
    menu_options = [
        ("1", "➕ Add new member", add_family_member),
        ("2", "📋 List all members", lambda: (list_family_members(), input("\nPress Enter to continue..."))),
        ("3", "✏️  Edit member", edit_family_member),
        ("4", "🗑️  Delete member", delete_family_member),
        ("5", "🔙 Back to main menu", None)
    ]
    
    while True:
        console.print("\n")
        console.print(Panel(
            "[bold cyan]Family Member Management[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE,
            expand=False,
            padding=(0, 2)
        ))
        
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
            
            if choice_index is None or choice_index == 4:
                break
            
            func = menu_options[choice_index][2]
            if func:
                func()
                
        except KeyboardInterrupt:
            console.print("\n[yellow]✗ Cancelled[/yellow]")
            break
