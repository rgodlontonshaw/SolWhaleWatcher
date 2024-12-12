import time
import os
from dotenv import load_dotenv
from checker import Checker
from discord_notif import DiscordNotifier
from whale_tracker import WhaleTracker
from collections import defaultdict

load_dotenv()

def main():
    API_KEY = os.getenv("API_KEY")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    WALLETS = os.getenv("WALLETS").split(',')

    HELIUS_API_URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"

    # Initialize classes
    checker = Checker(api_url=HELIUS_API_URL, wallets=WALLETS)
    discord_notifier = DiscordNotifier(webhook_url=DISCORD_WEBHOOK_URL)
    whale_tracker = WhaleTracker(api_url=HELIUS_API_URL, discord_notifier=discord_notifier)

    print("Starting tracking for wallets...\n")

    # Fetch initial holdings with a delay between wallets
    initial_holdings = {}
    for wallet in WALLETS:
        initial_holdings[wallet] = checker.fetch_wallet_data(wallet)
        time.sleep(1)  # Add a small delay between each wallet request

    print("Finished tracking initial state.\n")

    print("Starting to monitor changes...\n")
    while True:
        # Monitor wallet changes and check for common transactions
        transaction_records = {"buy": defaultdict(list), "sell": defaultdict(list)}
        for wallet in WALLETS:
            try:
                new_data = checker.fetch_wallet_data(wallet)
                changes = checker.monitor_changes(wallet, new_data, initial_holdings[wallet], transaction_records)
                if changes:
                    for change in changes:
                        print(change)
                initial_holdings[wallet] = new_data
            except Exception as e:
                print(f"Error monitoring wallet {wallet}: {str(e)}")
            time.sleep(1)

        # Check for tokens with more than 2 buyers or sellers
        for action, token_records in transaction_records.items():
            for token, wallets_involved in token_records.items():
                if len(wallets_involved) > 2:
                    if token == "So11111111111111111111111111111111111111112":
                        print(f"Skipping token {token} (excluded from tracking).")
                        continue
                    print(f"More than 2 wallets {action} token {token}, performing token analysis...")
                    message += f"More than 2 wallets detected performing action: {action}\n"
                    discord_notifier.send_notification(message)

        print("\nTracking whale activity...")
        whale_tracker.track_whale_activity(WALLETS)

        time.sleep(checker.FETCH_INTERVAL)

if __name__ == "__main__":
    main()