import requests
import json
from dotenv import load_dotenv
import os
from collections import defaultdict

# Load environment variables
load_dotenv()

# Constants
HELIUS_API_KEY = os.getenv("API_KEY")
if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY is missing. Please set it in the .env file.")
HELIUS_API_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
SUSPICIOUS_THRESHOLD_PERCENT = 35  # Top 20 holders owning >35% is flagged
MIN_LIQUIDITY = 100000             # Minimum liquidity (dummy value for now)
MIN_VOLUME = 50000                 # Minimum daily trading volume (dummy value for now)

class TokenAnalyzer:
    def __init__(self, api_url):
        self.api_url = api_url

    def fetch_token_supply(self, token_address):
        """
        Fetch total supply of a token using Helius API.
        """
        try:
            response = requests.post(
                self.api_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenSupply",
                    "params": [token_address]
                }
            )
            response.raise_for_status()
            data = response.json()
            supply_info = data.get("result", {}).get("value", {})
            total_supply = float(supply_info.get("uiAmount", 0))
            decimals = supply_info.get("decimals", 0)
            return total_supply, decimals
        except Exception as e:
            print(f"Error fetching token supply: {e}")
            return 0, 0

    def fetch_token_accounts(self, token_address):
        """
        Fetch all token accounts for a given mint address using Helius API.
        """
        try:
            page = 1
            limit = 1000
            all_accounts = []
            while True:
                response = requests.post(
                    self.api_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenAccounts",
                        "params": {
                            "mint": token_address,
                            "page": page,
                            "limit": limit,
                            "displayOptions": {"showZeroBalance": False}
                        }
                    }
                )
                response.raise_for_status()
                data = response.json()
                accounts = data.get("result", {}).get("tokenAccounts", [])
                if not accounts:
                    break
                all_accounts.extend(accounts)
                if len(accounts) < limit:
                    break
                page += 1
            return all_accounts
        except Exception as e:
            print(f"Error fetching token accounts: {e}")
            return []

    def aggregate_holder_balances(self, token_accounts, decimals):
        """
        Aggregate balances by holder address.
        """
        holder_balances = defaultdict(float)
        for account in token_accounts:
            owner = account.get("owner")
            amount = account.get("amount", 0) / (10 ** decimals)
            holder_balances[owner] += amount
        return holder_balances

    def get_top_holders(self, holder_balances, top_n=20):
        """
        Get the top N holders by balance.
        """
        sorted_holders = sorted(holder_balances.items(), key=lambda x: x[1], reverse=True)
        return sorted_holders[:top_n]

    def analyze_distribution(self, top_holders, total_supply):
        """
        Analyze the distribution of token holdings among top holders.
        """
        if not top_holders or total_supply == 0:
            return 0
        total_held_by_top = sum(balance for _, balance in top_holders)
        top_percent = (total_held_by_top / total_supply) * 100
        return round(top_percent, 2)

    def score_token(self, top_percent, liquidity, volume):
        """
        Score the token based on distribution thresholds.
        """
        if liquidity < MIN_LIQUIDITY or volume < MIN_VOLUME:
            return "Suspicious", "Low liquidity or trading volume."
        if top_percent > SUSPICIOUS_THRESHOLD_PERCENT:
            return "Suspicious", f"High concentration among top holders ({top_percent}%)."
        return "Potentially Good", "Token meets decentralization criteria."

    def analyze_token(self, token_address):
        """
        Main function to analyze a token.
        """
        total_supply, decimals = self.fetch_token_supply(token_address)
        if not total_supply:
            return {
                "status": "Error",
                "reason": "Failed to fetch token supply.",
                "total_supply": 0,
                "top_percent": 0,
                "top_holders": []
            }

        token_accounts = self.fetch_token_accounts(token_address)
        holder_balances = self.aggregate_holder_balances(token_accounts, decimals)
        top_holders = self.get_top_holders(holder_balances)
        top_percent = self.analyze_distribution(top_holders, total_supply)

        # Dummy values for liquidity and volume; replace with real data
        liquidity = 200000  # Replace with fetched liquidity data
        volume = 60000  # Replace with fetched volume data

        status, reason = self.score_token(top_percent, liquidity, volume)

        return {
            "token": token_address,
            "status": status,
            "reason": reason,
            "total_supply": round(total_supply, 2),
            "top_percent": top_percent,
            "top_holders": [{"address": addr, "balance": bal} for addr, bal in top_holders]
        }

