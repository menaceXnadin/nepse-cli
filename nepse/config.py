"""
Configuration management module.
Handles paths, file operations for config files.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

# Dynamic data directory for all credentials
# Uses user's Documents folder if available, otherwise home directory
DATA_DIR = Path.home() / "Documents" / "merosharedata"
if not DATA_DIR.parent.exists():
    DATA_DIR = Path.home() / "merosharedata"

DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "family_members.json"
IPO_CONFIG_FILE = DATA_DIR / "ipo_config.json"
CLI_HISTORY_FILE = DATA_DIR / "nepse_cli_history.txt"


def load_family_members() -> Dict:
    """Load all family members from config file"""
    if not CONFIG_FILE.exists():
        return {"members": []}
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def save_family_members(config: Dict) -> None:
    """Save family members to config file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    if os.name != 'nt':
        os.chmod(CONFIG_FILE, 0o600)


def get_member_by_name(member_name: str) -> Optional[Dict]:
    """Get a member by name (case-insensitive)"""
    config = load_family_members()
    for member in config.get('members', []):
        if member['name'].lower() == member_name.lower():
            return member
    return None


def get_all_members() -> List[Dict]:
    """Get all family members"""
    config = load_family_members()
    return config.get('members', [])


def add_member(member: Dict) -> None:
    """Add a new member to config"""
    config = load_family_members()
    if 'members' not in config:
        config['members'] = []
    config['members'].append(member)
    save_family_members(config)


def update_member(index: int, member: Dict) -> None:
    """Update a member at specific index"""
    config = load_family_members()
    if 0 <= index < len(config.get('members', [])):
        config['members'][index] = member
        save_family_members(config)


def delete_member(index: int) -> bool:
    """Delete a member at specific index"""
    config = load_family_members()
    members = config.get('members', [])
    if 0 <= index < len(members):
        members.pop(index)
        config['members'] = members
        save_family_members(config)
        return True
    return False


def load_ipo_config() -> Dict:
    """Load IPO application configuration"""
    if not IPO_CONFIG_FILE.exists():
        default_config = {
            "applied_kitta": 10,
            "crn_number": "YOUR_CRN_NUMBER_HERE"
        }
        with open(IPO_CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config
    
    with open(IPO_CONFIG_FILE, 'r') as f:
        return json.load(f)


def ensure_history_file() -> None:
    """Ensure CLI history file exists"""
    if not CLI_HISTORY_FILE.exists():
        CLI_HISTORY_FILE.touch()
