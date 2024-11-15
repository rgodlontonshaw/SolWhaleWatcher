import time
import requests
from collections import defaultdict
from dotenv import load_dotenv
import os

load_dotenv()


API_KEY = os.getenv('API_KEY')
HELIUS_API_URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"

# Discord webhook URL
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Wallet addresses to track
wallets = os.getenv("WALLETS").split(',')

wallet_holdings = {}

# Delay between API requests
FETCH_INTERVAL = 15  # Fetch every 15 seconds


def fetch_wallet_data(wallet_address):
    try:
        response = requests.post(
            HELIUS_API_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "getTokenAccountsByOwner", "params": [
                wallet_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]}
        )
        response.raise_for_status()
        data = response.json()

        balances = {}
        for account in data.get("result", {}).get("value", []):
            token = account["account"]["data"]["parsed"]["info"]["mint"]
            balance = float(account["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"])
            balances[token] = balance
        return balances
    except requests.exceptions.RequestException as e:
        print(f"Error fetching wallet data for {wallet_address}: {str(e)}")
        return {}


def send_discord_notification(message):
    try:
        payload = {"content": message}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Discord notification sent!")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Discord notification: {str(e)}")


def monitor_changes(wallet, new_data, initial_holdings, transaction_records):
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


def check_common_transactions(transaction_records):
    for action in ["buy", "sell"]:
        for token, wallet_list in transaction_records[action].items():
            if len(wallet_list) > 2:
                action_message = "bought" if action == "buy" else "sold"
                wallets_involved = ", ".join(wallet_list)
                message = f"ALERT: More than 2 wallets {action_message} token {token}!\nWallets: {wallets_involved}"
                send_discord_notification(message)


def main():
    print("Starting tracking for wallets...\n")

    initial_holdings = {wallet: fetch_wallet_data(wallet) for wallet in wallets}
    print("Finished tracking initial state.\n")

    print("Starting to monitor changes...\n")
    while True:
        transaction_records = {"buy": defaultdict(list), "sell": defaultdict(list)}
        for wallet in wallets:
            try:
                new_data = fetch_wallet_data(wallet)
                changes = monitor_changes(wallet, new_data, initial_holdings[wallet], transaction_records)
                if changes:
                    for change in changes:
                        print(change)
                initial_holdings[wallet] = new_data
            except Exception as e:
                print(f"Error monitoring wallet {wallet}: {str(e)}")

        check_common_transactions(transaction_records)
        time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()
