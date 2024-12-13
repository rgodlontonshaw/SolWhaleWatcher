import os
import json
import time
import requests
import websocket
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

class WebSocketTracker:
    def __init__(self, api_key, wallets, hummingbot_trigger):
        self.api_key = api_key
        self.wallets = wallets
        self.hummingbot_trigger = hummingbot_trigger
        self.token_holdings = defaultdict(dict)  # Store wallet token balances

    def on_message(self, ws, message):
        print("Raw message received:", message)  # Print raw WebSocket messages
        data = json.loads(message)
        print("Parsed message:", data)

        log_data = None  # Initialize log_data to avoid unbound local variable error
        if "method" in data and data["method"] == "logsNotification":
            log_data = data["params"]["result"]
            print("Transaction log received:", log_data)
            
            # Extract the transaction signature
            signature = log_data.get("signature")
            if signature:
                # Fetch detailed transaction data
                transaction_details = self.fetch_transaction_details(signature)
                if transaction_details:
                    print("Detailed transaction:", transaction_details)
                    self.process_transaction(transaction_details)

        if "method" in data and data["method"] == "accountNotification":
            print("Account notification received:", data["params"])
            # Process account notification here
        elif "error" in data:
            print("Error received:", data["error"])
        else:
            print("Subscription response or other message:", data)

        if log_data is not None:
            transaction = self.process_transaction(data)
            if transaction:
                self.analyze_transaction(transaction)


    def process_transaction(self, data):
        """Extract relevant transaction information."""
        # Parse the transaction data
        try:
            wallet = data.get("params", {}).get("result", {}).get("owner")
            token_address = data.get("params", {}).get("result", {}).get("tokenAddress")
            token_amount = float(data.get("params", {}).get("result", {}).get("amount", 0))
            usd_value = float(data.get("params", {}).get("result", {}).get("usdValue", 0))

            if wallet and token_address and token_amount > 0:
                return {
                    "wallet": wallet,
                    "token_address": token_address,
                    "token_amount": token_amount,
                    "usd_value": usd_value,
                }
        except Exception as e:
            print(f"Error processing transaction: {e}")
        return None

    def analyze_transaction(self, transaction):
        """Analyze the transaction for buy/sell actions and trigger conditions."""
        wallet = transaction["wallet"]
        token_address = transaction["token_address"]
        token_amount = transaction["token_amount"]
        usd_value = transaction["usd_value"]

        # Identify Buy or Sell
        if wallet not in self.token_holdings or token_address not in self.token_holdings[wallet]:
            print(f"BUY ORDER: Wallet: {wallet}, Token: {token_address}, Amount: {token_amount}, USD: {usd_value}")
            self.token_holdings[wallet][token_address] = token_amount  # Update holdings
        else:
            previous_amount = self.token_holdings[wallet][token_address]
            if token_amount > previous_amount:  # Buy detected
                print(f"BUY ORDER: Wallet: {wallet}, Token: {token_address}, Amount: {token_amount}, USD: {usd_value}")
            elif token_amount < previous_amount:  # Sell detected
                print(f"SELL ORDER: Wallet: {wallet}, Token: {token_address}, Amount: {token_amount}, USD: {usd_value}")
            self.token_holdings[wallet][token_address] = token_amount  # Update holdings

        # Trigger Hummingbot
        if usd_value > 10000 or usd_value > 0.5 * sum(self.token_holdings[wallet].values()):
            self.trigger_hummingbot(transaction)

    def trigger_hummingbot(self, transaction):
        """Trigger Hummingbot based on large transactions."""
        wallet = transaction["wallet"]
        token_address = transaction["token_address"]
        usd_value = transaction["usd_value"]
        print(f"HUMMINGBOT TRIGGERED: Whale {wallet} performed a large transaction on Token {token_address} worth ${usd_value}!")

    def start_websocket(self):
        """Start WebSocket connection to Helius API."""
        ws_url = f"wss://rpc.helius.xyz/?api-key={self.api_key}"

        def on_open(ws):
            print("WebSocket connection established.")
            # Subscribe to transactions for specific wallets
            wallets = [wallet.strip() for wallet in self.wallets]
            for wallet in self.wallets:
                subscription_message = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "accountSubscribe",
                    "params": [
                        wallet,
                        {"encoding": "jsonParsed"}
                    ]
                }
                print("Sending subscription message:", subscription_message)  # Debug
                ws.send(json.dumps(subscription_message))
                time.sleep(0.5)  

        def on_error(ws, error):
            print(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            print("WebSocket connection closed.")

        ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.on_open = on_open
        ws.run_forever()


if __name__ == "__main__":
    API_KEY = os.getenv("API_KEY")
    WALLETS = os.getenv("WALLETS").split(',')

    # Initialize tracker and start monitoring
    tracker = WebSocketTracker(api_key=API_KEY, wallets=WALLETS, hummingbot_trigger=True)
    tracker.start_websocket()
