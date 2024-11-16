import requests
from collections import defaultdict
import time

class Checker:

    def __init__(self, api_url, wallets):
        self.api_url = api_url
        self.wallets = wallets
        self.wallet_holdings = {}
        self.FETCH_INTERVAL = 15 # fetch every 15 seconds

    def fetch_wallet_data(self, wallet_address, max_retries=5):
        retries = 0
        while retries < max_retries:
            try:
                response = requests.post(
                    self.api_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenAccountsByOwner",
                        "params": [
                            wallet_address,
                            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                            {"encoding": "jsonParsed"},
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Parse token balances
                balances = {}
                for account in data.get("result", {}).get("value", []):
                    token = account["account"]["data"]["parsed"]["info"]["mint"]
                    balance = float(account["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"])
                    balances[token] = balance
                return balances
            except requests.exceptions.RequestException as e:
                print(f"Error fetching wallet data for {wallet_address}: {str(e)}")
                retries += 1
                if retries < max_retries:
                    wait_time = 2 ** retries  # Exponential backoff
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Skipping this wallet.")
                    return {}

    def monitor_changes(self, wallet, new_data, initial_holdings, transaction_records):
        changes = []
        for token, new_balance in new_data.items():
            old_balance = initial_holdings.get(token, 0)
            if new_balance > old_balance:
                if old_balance == 0:
                    changes.append(
                        f"Wallet {wallet} bought: {token}, New Balance: {round(new_balance, 3)} (New holding: 100%)"
                    )
                    transaction_records["buy"][token].append(wallet)
                else:
                    percent_change = ((new_balance - old_balance) / old_balance) * 100
                    changes.append(
                        f"Wallet {wallet} bought: {token}, Old Balance: {round(old_balance, 3)}, New Balance: {round(new_balance, 3)} (+{round(percent_change, 2)}%)"
                    )
                    transaction_records["buy"][token].append(wallet)
            elif new_balance < old_balance:
                percent_change = ((old_balance - new_balance) / old_balance) * 100
                changes.append(
                    f"Wallet {wallet} sold: {token}, Old Balance: {round(old_balance, 3)}, New Balance: {round(new_balance, 3)} (-{round(percent_change, 2)}%)"
                )
                transaction_records["sell"][token].append(wallet)
        return changes


    def check_common_transactions(self, transaction_records, discord_notifier):
        for action in ["buy", "sell"]:
            for token, wallet_list in transaction_records[action].items():
                if len(wallet_list) > 2:
                    action_message = "bought" if action == "buy" else "sold"
                    wallets_involved = ", ".join(wallet_list)
                    message = f"ALERT: More than 2 wallets {action_message} token {token}!\nWallets: {wallets_involved}"
                    discord_notifier.send_notifications(message)


