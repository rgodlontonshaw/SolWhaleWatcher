import requests

class WhaleTracker:
    def __init__(self, api_url, discord_notifier):
        self.api_url = api_url
        self.discord_notifier = discord_notifier
        self.transaction_threshold = 1000  # Threshold in USD for whale transactions

    def fetch_recent_transactions_for_wallets(self, wallets):
        """
        Fetch recent transactions for a list of whale wallets.
        """
        transactions = []
        for wallet in wallets:
            try:
                response = requests.post(
                    self.api_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSignaturesForAddress",
                        "params": [wallet]
                    }
                )
                response.raise_for_status()
                data = response.json()
                transactions.extend(data.get("result", []))
            except Exception as e:
                print(f"Error fetching transactions for wallet {wallet}: {e}")
        return transactions

    def analyze_whale_transactions(self, transactions):
        """
        Analyze whale transactions based on the transaction threshold.
        """
        whale_transactions = []
        for tx in transactions:
            amount = tx.get("amount", 0)
            if amount >= self.transaction_threshold:
                whale_transactions.append(tx)
        return whale_transactions

    def track_whale_activity(self, whale_wallets):
        """
        Track and flag whale activity across wallets.
        """
        transactions = self.fetch_recent_transactions_for_wallets(whale_wallets)
        if not transactions:
            print("No recent transactions available.")
            return

        whale_transactions = self.analyze_whale_transactions(transactions)

        if whale_transactions:
            alert_message = "⚠️ Whale Activity Detected:\n"
            for tx in whale_transactions:
                tx_info = f"- Wallet: {tx['wallet']}, Transaction: {tx['signature']}, Amount: {tx['amount']}"
                alert_message += tx_info + "\n"

            self.discord_notifier.send_notification(alert_message)
            print("Whale activity alert sent to Discord!")
        else:
            print("No significant whale activity detected.")

if __name__ == "__main__":
    api_url = "https://api.helius.xyz/rpc"
    discord_notifier = "https://discord.com/api/webhooks/1316203213904674876/92pAC4yFDL3rAbWH6TfyWXkQnKknZjWeNjZDtU111m6Ua-3J9iYp56_4_9wZuyK4OPAs"  # Replace with actual Discord notifier instance

    tracker = WhaleTracker(api_url, discord_notifier)
    # whale_wallets = ["2pekTQKDsJkd7qUMVD6Z5AGdUuuQ2ZF7zGDmhKjjgVdr", "2zTqUBQMjQXjPTbWyNSdgQgNDcV5isnVF3oqR2nhfjj3", "4t9bWuZsXXKGMgmd96nFD4KWxyPNTsPm4q9jEMH4jD2i","D4zVhwuUsFbcaty7wJhNEZ7VEwPHXQ5d2heXPxM5yWhL","7g34jSNJRSdYiRMZAyP8ZkLycVxhayJvTa4vZ1BQ44Kx","9dzWEg3mf2APiscAMNP298VwANwYz3h4BDutfMEjGSfN"]  # Replace with actual whale wallets

    # tracker.track_whale_activity(whale_wallets)

    tracker.track_whale_activity(WALLETS)
