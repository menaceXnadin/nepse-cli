"""
Nepse CLI - Entry point wrapper for the main CLI application
This file provides the console script entry point for the installed package.
"""
import sys


def main():
    """CLI entry point - runs the interactive menu."""
    try:
        from main import main as interactive_menu
        interactive_menu()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
