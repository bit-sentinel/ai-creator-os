#!/usr/bin/env python3
"""
Seed accounts from config/accounts.yaml into Supabase.
Run once after setting up your .env and database.

Usage:
    python scripts/setup_accounts.py
    python scripts/setup_accounts.py --token "EAAx..." --ig-user-id "17841400..." --username ai_growth_hacks
"""
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from services import supabase_client as db


def seed_from_yaml():
    with open("config/accounts.yaml") as f:
        cfg = yaml.safe_load(f)

    accounts = cfg.get("accounts", [])
    print(f"\nSeeding {len(accounts)} accounts...\n")

    for acc in accounts:
        try:
            saved = db.upsert_account(acc)
            print(f"  ✓ {acc['username']} ({acc['niche']}) — ID: {saved['account_id']}")
        except Exception as e:
            print(f"  ✗ {acc['username']}: {e}")


def set_credentials(username: str, token: str, ig_user_id: str):
    """Attach Instagram credentials to an existing account."""
    accounts = db.get_active_accounts()
    account = next((a for a in accounts if a["username"] == username), None)
    if not account:
        print(f"Account '{username}' not found. Run seed first.")
        sys.exit(1)

    db.upsert_account({
        "account_id": account["account_id"],
        "username": username,
        "niche": account["niche"],
        "access_token": token,
        "instagram_user_id": ig_user_id,
        "status": "active",
    })
    print(f"  ✓ Credentials updated for '{username}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Creator OS account setup")
    parser.add_argument("--seed", action="store_true", default=True,
                        help="Seed accounts from accounts.yaml (default)")
    parser.add_argument("--username", type=str, help="Account username for credential update")
    parser.add_argument("--token", type=str, help="Instagram long-lived access token")
    parser.add_argument("--ig-user-id", type=str, help="Instagram User ID (numeric)")
    args = parser.parse_args()

    if args.username and args.token and args.ig_user_id:
        set_credentials(args.username, args.token, args.ig_user_id)
    else:
        seed_from_yaml()
