
"""
Nepse CLI - Entry point wrapper for the main CLI application
This file is kept minimal to avoid requiring reinstalls when editing command logic.
All command implementations are in main.py.
"""
import sys
from main import (
    # Core automation functions
    apply_ipo,
    add_family_member,
    list_family_members,
    edit_family_member,
    delete_family_member,
    manage_family_members,
    select_family_member,
    get_portfolio_for_member,
    test_login_for_member,
    get_dp_list,
    apply_ipo_for_all_members,
    load_family_members,
    main as interactive_menu,
    # Market data commands
    cmd_ipo,
    cmd_nepse,
    cmd_subidx,
    cmd_mktsum,
    cmd_topgl,
    cmd_stonk,
    # Parser functions
    build_parser,
)


def main():
    """CLI entry point - delegates to build_parser and command handlers in main.py"""
    parser = build_parser()
    args = parser.parse_args()
    
    # If no command provided, run interactive menu
    if not args.command:
        try:
            interactive_menu()
        except KeyboardInterrupt:
            print("\n\nExiting...")
            sys.exit(0)
        return
    
    # Execute commands by delegating to main.py functions
    try:
        if args.command == "apply":
            apply_ipo(auto_load=True, headless=True)
        elif args.command == "status":
            print("IPO status check not yet implemented")
        elif args.command == "add-member":
            add_family_member()
        elif args.command == "list-members":
            list_family_members()
            input("\nPress Enter to continue...")
        elif args.command == "test-login":
            if hasattr(args, 'member_id') and args.member_id:
                member = select_family_member()
            else:
                member = select_family_member()
            if member:
                test_login_for_member(member, headless=True)
        elif args.command == "get-portfolio":
            if hasattr(args, 'member_id') and args.member_id:
                member = select_family_member()
            else:
                member = select_family_member()
            if member:
                get_portfolio_for_member(member, headless=True)
        elif args.command == "dplist":
            get_dp_list()
        elif args.command == "ipo":
            cmd_ipo()
        elif args.command == "nepse":
            cmd_nepse()
        elif args.command == "subidx":
            cmd_subidx(args.name)
        elif args.command == "mktsum":
            cmd_mktsum()
        elif args.command == "topgl":
            cmd_topgl()
        elif args.command == "stonk":
            cmd_stonk(args.symbol)
        elif args.command == "interactive":
            interactive_menu()
        else:
            print(f"Unknown command: {args.command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n Cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
