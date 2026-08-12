"""
Investopedia Simulator Automated Execution Client for AlphaPulse.
Uses Playwright to automate login, portfolio retrieval, and trade execution (BUY/SELL)
on the Investopedia Stock Simulator.
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv

# Try importing Playwright
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

logger = logging.getLogger("investopedia_client")

load_dotenv()

INVESTOPEDIA_EMAIL = os.getenv("INVESTOPEDIA_EMAIL", "")
INVESTOPEDIA_PASSWORD = os.getenv("INVESTOPEDIA_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

SIMULATOR_URL = "https://www.investopedia.com/simulator"
LOGIN_URL = "https://www.investopedia.com/auth/realms/investopedia/protocol/openid-connect/auth"

SESSION_STATE_PATH = os.path.join(os.path.dirname(__file__), "session_state.json")

class InvestopediaClient:
    def __init__(self, email=None, password=None, headless=True):
        self.email = email or INVESTOPEDIA_EMAIL
        self.password = password or INVESTOPEDIA_PASSWORD
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None

    def start_session(self):
        """Launches Playwright Chromium browser session with persistent session state if available."""
        if not sync_playwright:
            raise RuntimeError("Playwright is not installed. Please run: pip install playwright && playwright install chromium")
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        
        # Load saved session state if exists to bypass 2FA on future runs
        if os.path.exists(SESSION_STATE_PATH):
            logger.info("Found saved session_state.json — loading authenticated cookies...")
            self.context = self.browser.new_context(
                storage_state=SESSION_STATE_PATH,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
        else:
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
        
        self.page = self.context.new_page()

    def save_session_state(self):
        """Saves current browser cookies and localStorage to session_state.json."""
        try:
            if self.context:
                self.context.storage_state(path=SESSION_STATE_PATH)
                logger.info("✓ Saved persistent session state to session_state.json!")
        except Exception as e:
            logger.warning(f"Could not save session state: {e}")

    def close_session(self):
        """Closes browser session."""
        try:
            if self.browser:
                self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser session: {e}")

    def login(self):
        """Logs into Investopedia Simulator and handles 2FA verification if required."""
        if not self.email or not self.password:
            logger.warning("Investopedia credentials missing. Set INVESTOPEDIA_EMAIL and INVESTOPEDIA_PASSWORD in .env")
            return False

        logger.info(f"Checking Investopedia session status for {self.email}...")
        try:
            self.page.goto(SIMULATOR_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # If already logged in via session_state.json, we're done!
            if "simulator" in self.page.url.lower() and not self.page.is_visible("text=Log In"):
                logger.info("✓ Already authenticated via saved session state!")
                return True

            # Check if login button/link exists
            if self.page.is_visible("text=Log In") or self.page.is_visible("a[href*='login']"):
                self.page.click("text=Log In")
                time.sleep(2)

            # Fill username/email
            if self.page.is_visible("input[name='username']") or self.page.is_visible("input[type='email']"):
                email_input = self.page.locator("input[name='username'], input[type='email']").first
                email_input.fill(self.email)
                
                if self.page.is_visible("button:has-text('Next')"):
                    self.page.click("button:has-text('Next')")
                    time.sleep(1)

                password_input = self.page.locator("input[name='password'], input[type='password']").first
                password_input.fill(self.password)
                
                submit_btn = self.page.locator("button[type='submit'], input[type='submit'], button:has-text('Log In')").first
                submit_btn.click()
                time.sleep(4)

            # Handle 2FA / Passcode verification prompt if triggered
            if self.page.is_visible("input[name*='code']") or self.page.is_visible("input[id*='otp']") or self.page.is_visible("text=Verification"):
                logger.warning("🔐 Investopedia requested a 2FA Verification Code!")
                if not self.headless:
                    print("\n" + "="*80)
                    print("🔐 2FA VERIFICATION REQUIRED: Please enter the verification code in the browser window or terminal!")
                    code = input("Enter 2FA Code received via Email/SMS: ").strip()
                    print("="*80 + "\n")
                    
                    code_input = self.page.locator("input[name*='code'], input[id*='otp'], input[type='text']").first
                    code_input.fill(code)
                    
                    verify_btn = self.page.locator("button[type='submit'], button:has-text('Verify'), input[value*='Verify']").first
                    if verify_btn.is_visible():
                        verify_btn.click()
                        time.sleep(4)

            # Save session cookies for future headless runs
            self.save_session_state()
            logger.info("Successfully logged into Investopedia Simulator!")
            return True
        except Exception as e:
            logger.error(f"Error logging into Investopedia: {e}")
            return False

    def execute_trade(self, ticker, action, shares):
        """
        Submits a trade order (BUY or SELL) on Investopedia.
        
        Parameters:
            ticker (str): Stock symbol (e.g. 'NVDA')
            action (str): 'BUY' or 'SELL'
            shares (int): Number of shares
        """
        if not self.page:
            raise RuntimeError("Session not started. Call start_session() and login() first.")

        ticker = ticker.upper()
        action = action.upper()
        shares = int(shares)

        if shares <= 0:
            logger.warning(f"Trade skipped for {ticker}: shares must be > 0")
            return False

        logger.info(f"Executing Investopedia order: {action} {shares} shares of {ticker}")
        try:
            # Navigate to trade page
            self.page.goto("https://www.investopedia.com/simulator/trade/tradestock.aspx", wait_until="networkidle")
            time.sleep(2)

            # Enter Ticker Symbol
            symbol_input = self.page.locator("input[id*='symbol'], input[name*='symbol'], input[placeholder*='Symbol']").first
            symbol_input.fill(ticker)
            time.sleep(1)
            self.page.keyboard.press("Enter")
            time.sleep(2)

            # Select Buy or Sell
            if action == "BUY":
                if self.page.is_visible("input[value='Buy'], button:has-text('Buy')"):
                    self.page.click("input[value='Buy'], button:has-text('Buy')")
            else:
                if self.page.is_visible("input[value='Sell'], button:has-text('Sell')"):
                    self.page.click("input[value='Sell'], button:has-text('Sell')")

            # Enter Share Quantity
            quantity_input = self.page.locator("input[id*='quantity'], input[name*='quantity']").first
            quantity_input.fill(str(shares))
            time.sleep(1)

            # Submit Order Preview & Confirm
            preview_btn = self.page.locator("button:has-text('Preview Order'), input[value*='Preview']").first
            if preview_btn.is_visible():
                preview_btn.click()
                time.sleep(2)

            submit_btn = self.page.locator("button:has-text('Submit Order'), input[value*='Submit']").first
            if submit_btn.is_visible():
                submit_btn.click()
                time.sleep(2)

            logger.info(f"✓ Trade Order Submitted: {action} {shares} {ticker}")
            return True
        except Exception as e:
            logger.error(f"Failed to execute trade for {ticker}: {e}")
            return False
