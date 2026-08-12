#!/usr/bin/env python3
"""
Interactive 1-Time Session Login & 2FA Setup Script for Investopedia Auto-Trader.
Opens an interactive (visible) Chromium browser window to log in, handle 2FA passcode,
and save session cookies to investopedia_executor/session_state.json.

Once completed, all future daily automated runs will use the saved session state
and bypass 2FA prompts automatically in headless mode!
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from investopedia_executor.investopedia_client import InvestopediaClient, SESSION_STATE_PATH

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

def main():
    print("=" * 80)
    print("🔐 ALPHAPULSE INVESTOPEDIA 1-TIME 2FA SESSION INITIALIZER")
    print("=" * 80)
    print(" This script will open a visible Chromium browser window.")
    print(" 1. It will navigate to Investopedia Simulator.")
    print(" 2. Enter your credentials and type the 2FA code in the browser window.")
    print(" 3. Upon successful login, it saves session_state.json so future automated runs")
    print("    will BYPASS 2FA automatically in background mode!")
    print("=" * 80 + "\n")

    email = os.getenv("INVESTOPEDIA_EMAIL")
    password = os.getenv("INVESTOPEDIA_PASSWORD")

    if not email or not password:
        email = input("Enter Investopedia Email: ").strip()
        password = input("Enter Investopedia Password: ").strip()

    client = InvestopediaClient(email=email, password=password, headless=False)
    try:
        client.start_session()
        success = client.login()
        if success:
            client.save_session_state()
            print("\n" + "=" * 80)
            print(f"🎉 SUCCESS! Saved authenticated session to {SESSION_STATE_PATH}")
            print(" All future daily auto-trader runs will now run headlessly without 2FA prompts!")
            print("=" * 80 + "\n")
        else:
            print("❌ Login attempt failed. Please check your credentials or 2FA entry.")
    except Exception as e:
        print(f"❌ Error during login session: {e}")
    finally:
        client.close_session()

if __name__ == "__main__":
    main()
