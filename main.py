import time
import os
from dotenv import load_dotenv
from checker import Checker
from discord_notif import DiscordNotifier
from collections import defaultdict


load_dotenv()


def main():
    api_key = os.getenv("API_KEY")
    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    wallets = os.getenv("WALLETS").split(',')

    helius_api_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"

    # Initialize classes
    checker = Checker(api_url=helius_api_url, wallets=wallets)
    discord_notifier = DiscordNotifier(webhook_url=discord_webhook_url)
    print("Starting tracking for wallets...\n")

    initial_holdings = {wallet: checker.fetch_wallet_data(wallet) for wallet in wallets}
    print("Finished tracking initial state.\n")

    print("Starting to monitor changes...\n")
    while True:
        transaction_records = {"buy": defaultdict(list), "sell": defaultdict(list)}
        for wallet in wallets:
            try:
                new_data = checker.fetch_wallet_data(wallet)
                changes = checker.monitor_changes(wallet, new_data, initial_holdings[wallet], transaction_records)
                if changes:
                    for change in changes:
                        print(change)
                initial_holdings[wallet] = new_data
            except Exception as e:
                print(f"Error monitoring wallet {wallet}: {str(e)}")

        checker.check_common_transactions(transaction_records, discord_notifier)
        time.sleep(checker.FETCH_INTERVAL)


if __name__ == "__main__":
    main()
