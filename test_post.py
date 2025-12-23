import json
import time
import requests
import getpass
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# ==========================================
# Constants
# ==========================================
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"
MS_API_BASE = "https://webbackend.cdsc.com.np/api"

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/json",
    "Origin": "https://meroshare.cdsc.com.np",
    "Connection": "keep-alive",
    "Referer": "https://meroshare.cdsc.com.np/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

# ==========================================
# Errors
# ==========================================
class LocalException(Exception):
    def __init__(self, message: str):
        self.message = message
    def __str__(self):
        return self.message

class GlobalError(Exception):
    def __init__(self, message: str):
        self.message = message
    def __str__(self):
        return self.message

# ==========================================
# Portfolio Models
# ==========================================
class PortfolioEntry:
    def __init__(self, **kwargs):
        self.current_balance = float(kwargs.get("currentBalance", 0))
        self.last_transaction_price = float(kwargs.get("lastTransactionPrice", 0))
        self.previous_closing_price = float(kwargs.get("previousClosingPrice", 0))
        self.script = kwargs.get("script")
        self.script_desc = kwargs.get("scriptDesc")
        self.value_as_of_last_transaction_price = float(kwargs.get("valueAsOfLastTransactionPrice", 0))
        self.value_as_of_previous_closing_price = float(kwargs.get("valueAsOfPreviousClosingPrice", 0))

    def to_json(self):
        return {
            "current_balance": self.current_balance,
            "last_transaction_price": self.last_transaction_price,
            "previous_closing_price": self.previous_closing_price,
            "script": self.script,
            "script_desc": self.script_desc,
            "value_as_of_last_transaction_price": self.value_as_of_last_transaction_price,
            "value_as_of_previous_closing_price": self.value_as_of_previous_closing_price,
        }

class Portfolio:
    def __init__(self, entries, total_items, total_val_ltp, total_val_prev):
        self.entries = entries
        self.total_items = total_items
        self.total_value_as_of_last_transaction_price = total_val_ltp
        self.total_value_as_of_previous_closing_price = total_val_prev

    def to_json(self):
        return {
            "entries": [entry.to_json() for entry in self.entries],
            "total_items": self.total_items,
            "total_value_as_of_last_transaction_price": self.total_value_as_of_last_transaction_price,
            "total_value_as_of_previous_closing_price": self.total_value_as_of_previous_closing_price,
        }

# ==========================================
# Helper Functions
# ==========================================
def fetch_capital_id(dpid_code: str) -> int:
    """Fetch Capital ID from DPID Code (e.g. '10900' -> 190)"""
    print(f'🔍 Looking up Capital ID for DPID: {dpid_code}...')
    try:
        response = requests.get(f"{MS_API_BASE}/meroShare/capital/", headers=BASE_HEADERS)
        if response.status_code == 200:
            capitals = response.json()
            for cap in capitals:
                if cap.get('code') == str(dpid_code):
                    print(f"   ✅ Found Capital: {cap.get('name')} (ID: {cap.get('id')})")
                    return cap.get('id')
    except Exception as e:
        print(f"   ❌ Error fetching capitals: {e}")
    
    raise GlobalError(f"Could not find Capital ID for DPID {dpid_code}")

# ==========================================
# Account Class
# ==========================================
class Account:
    def __init__(
        self,
        username: str,
        password: str,
        dpid_code: str,
        capital_id: int,
    ):
        self.username = username
        self.password = password
        self.dpid_code = dpid_code # "10900"
        self.capital_id = capital_id
        
        self.dmat = None # Will be fetched
        self.name = None
        self.auth_token = None
        self.portfolio = None

        self.__session = requests.Session()
        self.__session.headers.update(BASE_HEADERS)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def login(self) -> str:
        data = {
            "clientId": str(self.capital_id),
            "username": self.username,
            "password": self.password,
        }

        headers = BASE_HEADERS.copy()
        headers["Authorization"] = "null"
        headers["Content-Type"] = "application/json"

        print('🔄 Logging in...')
        login_req = requests.post(f"{MS_API_BASE}/meroShare/auth/", json=data, headers=headers)
        
        if login_req.status_code != 200:
            print(f"❌ Login failed: {login_req.status_code}")
            raise LocalException(f"Login failed!")

        self.auth_token = login_req.headers.get("Authorization")
        self.__session.headers.update({"Authorization": self.auth_token})
        
        print(f'✅ Login successful!')
        return self.auth_token

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_own_details(self):
        """Fetch user details to get Demat number"""
        print('👤 Fetching own details...')
        headers = BASE_HEADERS.copy()
        headers["Authorization"] = self.auth_token
        
        # This endpoint returns the logged-in user's details
        response = requests.get(f"{MS_API_BASE}/meroShare/ownDetail/", headers=headers)

        if response.status_code == 200:
            data = response.json()
            self.dmat = data.get('demat')
            self.name = data.get('name')
            print(f'✅ Found Demat: {self.dmat}')
            print(f'✅ Found Name: {self.name}')
            return data
        else:
            raise LocalException(f"Failed to fetch own details: {response.status_code}")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_portfolio(self) -> Portfolio:
        if not self.dmat:
            self.fetch_own_details()
            
        print('💼 Fetching portfolio...')
        headers = BASE_HEADERS.copy()
        headers["Authorization"] = self.auth_token
        headers["Content-Type"] = "application/json"
        
        # Use dpid_code (e.g. "10900") as clientCode
        payload = {
            "sortBy": "script",
            "demat": [self.dmat],
            "clientCode": self.dpid_code, 
            "page": 1,
            "size": 200,
            "sortAsc": True,
        }
        
        portfolio_req = requests.post(
            f"{MS_API_BASE}/meroShareView/myPortfolio/",
            json=payload,
            headers=headers
        )

        if portfolio_req.status_code != 200:
            print(f"❌ Portfolio request failed: {portfolio_req.status_code}")
            raise LocalException(f"Portfolio request failed!")

        data = portfolio_req.json()
        
        entries = [PortfolioEntry(**item) for item in data.get("meroShareMyPortfolio", [])]
        
        new_portfolio = Portfolio(
            entries=entries,
            total_items=data.get("totalItems"),
            total_val_ltp=float(data.get("totalValueAsOfLastTransactionPrice")),
            total_val_prev=float(data.get("totalValueAsOfPreviousClosingPrice")),
        )

        self.portfolio = new_portfolio
        return new_portfolio

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_wacc_report(self):
        """
        Fetch WACC report from myPurchase API.

        This mirrors the portfolio request: uses the logged-in user's demat and DPID
        and POSTs to `/api/myPurchase/waccReport/`.
        """
        if not self.dmat:
            self.fetch_own_details()

        print('📊 Fetching WACC report...')
        headers = BASE_HEADERS.copy()
        headers["Authorization"] = self.auth_token
        headers["Content-Type"] = "application/json"

        # WACC endpoint expects only the demat in the body, e.g. {"demat": "1301610001664007"}
        payload = {
            "demat": self.dmat,
        }

        wacc_req = requests.post(
            f"{MS_API_BASE}/myPurchase/waccReport/",
            json=payload,
            headers=headers,
        )

        if wacc_req.status_code != 200:
            print(f"❌ WACC report request failed: {wacc_req.status_code}")
            try:
                print(f"   Response body: {wacc_req.text}")
            except Exception:
                pass
            raise LocalException("WACC report request failed!")

        try:
            data = wacc_req.json()
        except Exception:
            print("❌ Failed to parse WACC response as JSON, raw body below:")
            print(wacc_req.text)
            raise

        return data

# ==========================================
# Main Execution
# ==========================================
def main():
    print('='*70)
    print('MeroShare Portfolio - Dynamic CLI')
    print('='*70)
    
    # Initialize variables
    dpid_code = ""
    username = ""
    password = ""
    
    # Interactive Input
    print("\n🔐 Please enter your credentials:")
    print("   (Press Enter to skip and try loading from payload.json)")
    
    dpid_input = input(f"   DPID Code (e.g. 10900): ").strip()
    if dpid_input:
        dpid_code = dpid_input
        username = input(f"   Username: ").strip()
        password = getpass.getpass(f"   Password: ").strip()
    
    # Fallback to payload.json if inputs are empty
    if not dpid_code or not username or not password:
        print("\n⚠️  Inputs empty, checking payload.json...")
        try:
            with open('payload.json', 'r') as f:
                creds = json.load(f)
                if not username: username = creds.get('username')
                if not password: password = creds.get('password')
                # Try to guess DPID if not provided (defaulting to 10900 for now or extracting from demat)
                if not dpid_code: 
                    demat = creds.get('demat', '')
                    if demat and len(demat) == 16:
                        dpid_code = demat[3:8]
                    else:
                        dpid_code = "10900" # Default fallback
                print("   ✅ Loaded credentials from payload.json")
        except FileNotFoundError:
            print("   ❌ payload.json not found.")
    
    # Final Validation
    if not dpid_code or not username or not password:
        print("\n❌ Error: Missing credentials! Please provide inputs.")
        return

    print(f'\n🚀 Starting Session for User: {username} (DPID: {dpid_code})')
    print('-'*70)

    try:
        # 1. Get Capital ID from DPID Code
        capital_id = fetch_capital_id(dpid_code)
        
        # 2. Initialize Account
        account = Account(
            username=str(username),
            password=password,
            dpid_code=dpid_code,
            capital_id=capital_id
        )
        
        # 3. Login
        account.login()
        time.sleep(1)
        
        # 4. Fetch Details (Demat)
        account.fetch_own_details()
        time.sleep(1)
        
        # 5. Fetch Portfolio
        portfolio = account.fetch_portfolio()
        
        # 6. Fetch WACC Report
        wacc_report = account.fetch_wacc_report()
        
        print('\n' + '='*70)
        print('✅ SUCCESS! Portfolio Fetched')
        print('='*70)
        
        print(f'\n📈 Summary:')
        print(f'   Total Items: {portfolio.total_items}')
        print(f'   Total Value: Rs. {portfolio.total_value_as_of_last_transaction_price:,.2f}')
        
        print(f'\n📋 Holdings:')
        print(f'   {"Script":<10} {"Balance":<10} {"LTP":<10} {"Value":<15}')
        print(f'   {"-"*50}')
        for entry in portfolio.entries:
            print(f'   {entry.script:<10} {entry.current_balance:<10} {entry.last_transaction_price:<10} {entry.value_as_of_last_transaction_price:<15,.2f}')
            
        # Save portfolio to file
        portfolio_filename = f'portfolio_{username}.json'
        with open(portfolio_filename, 'w') as f:
            json.dump(portfolio.to_json(), f, indent=2)
        print(f'\n💾 Saved portfolio to {portfolio_filename}')

        # Save WACC report to file (raw JSON)
        wacc_filename = f'wacc_report_{username}.json'
        with open(wacc_filename, 'w') as f:
            json.dump(wacc_report, f, indent=2)
        print(f'💾 Saved WACC report to {wacc_filename}')

    except Exception as e:
        print(f'\n❌ Error: {e}')
        # import traceback
        # traceback.print_exc()

if __name__ == '__main__':
    main()