import requests


class WhaleTracker:
    def __init__(self, api_url, discord_notifier):
        self.api_url = api_url
        self.discord_notifier = discord_notifier
        self.transaction_threshold = 10000  # Example threshold in token units

    def fetch_recent_transactions(self, token_address):
        """
        Fetch recent transactions for the token using Helius API.
        """
        try:
            response = requests.post(
                self.api_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenLargestAccounts",
                    "params": [token_address]
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("result", [])
        except Exception as e:
            print(f"Error fetching recent transactions: {e}")
            return []

    def analyze_transactions(self, transactions, token_supply, decimals):
        """
        Analyze transactions for whale activity.
        """
        whale_transactions = []
        for tx in transactions:
            amount = tx.get("amount", 0) / (10 ** decimals)
            if amount >= self.transaction_threshold or (amount / token_supply) * 100 >= 1:
                whale_transactions.append(tx)

        return whale_transactions

    def track_whale_activity(self, token_address, token_supply, decimals):
        """
        Main function to track and flag whale activity.
        """
        transactions = self.fetch_recent_transactions(token_address)
        if not transactions:
            print("No recent transactions available.")
            return

        whale_transactions = self.analyze_transactions(transactions, token_supply, decimals)

        if whale_transactions:
            alert_message = f"⚠️ Whale Activity Detected for {token_address}:\n"
            for tx in whale_transactions:
                tx_info = f"- Transaction: {tx['signature']}, Amount: {tx.get('amount', 0)}"
                alert_message += tx_info + "\n"
            self.discord_notifier.send_notification(alert_message)
            print("Whale activity alert sent to Discord!")
        else:
            print("No significant whale activity detected.")
