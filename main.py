import os
import json
import requests
import time
from websocket import create_connection

class SolanaWalletMonitor:
    def __init__(self, http_url, wss_url, wallets):
        """
        :param http_url:  HTTP endpoint (Helius or standard Solana RPC)
        :param wss_url:   WebSocket endpoint (Helius or standard Solana WS)
        :param wallets:   List of wallet addresses to monitor
        """
        self.http_url = http_url
        self.wss_url = wss_url
        self.wallets = wallets

        # Store "previous known" token balances for each wallet:
        # balances_dict = {
        #    wallet_address: { token_mint: amount_float, ... }
        # }
        self.balances_dict = {}

        # WebSocket connection
        self.ws = None

    def start(self):
        """Entry point to initialize balances and begin WebSocket subscription."""
        # 1) Initialize baseline balances
        self._init_wallet_balances()

        # 2) Connect WebSocket
        self.ws = create_connection(self.wss_url)
        print(f"WebSocket connected to {self.wss_url}")

        # 3) Subscribe logs for each wallet
        for w in self.wallets:
            sub_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "logsSubscribe",
                "params": [
                    {"mentions": [w]},
                    {"encoding": "jsonParsed"}
                ]
            }
            self.ws.send(json.dumps(sub_msg))

        print("WebSocket subscribed to logs for wallets:", self.wallets)

        # 4) Listen for real-time logs
        self._listen_loop()

    def _init_wallet_balances(self):
        """Fetch each wallet's token balances once, store them for baseline."""
        for wallet in self.wallets:
            self.balances_dict[wallet] = self._fetch_token_balances(wallet)

    def _fetch_token_balances(self, wallet):
        """
        Using `getTokenAccountsByOwner` to retrieve SPL token accounts for `wallet`.
        Returns { mint: ui_amount }.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                wallet,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]
        }

        try:
            resp = requests.post(self.http_url, json=payload).json()
            accounts = resp.get("result", {}).get("value", [])
            token_balances = {}
            for account in accounts:
                info = account["account"]["data"]["parsed"]["info"]
                mint = info["mint"]
                amount_str = info["tokenAmount"]["amount"]
                decimals = info["tokenAmount"]["decimals"]
                ui_amount = float(amount_str) / (10 ** decimals)
                token_balances[mint] = ui_amount
            return token_balances
        except Exception as e:
            print(f"Error fetching token balances for {wallet}: {e}")
            return {}

    def _listen_loop(self):
        """Continuously receive log messages, parse and detect buy/sell changes."""
        while True:
            try:
                message = self.ws.recv()
                self._handle_logs_message(message)
            except Exception as e:
                print("WebSocket error:", e)
                time.sleep(5)  # wait & retry

    def _handle_logs_message(self, message):
        """Called when WebSocket receives logs. Extract the tx signature & parse changes."""
        msg = json.loads(message)
        if "method" in msg and msg["method"] == "logsNotification":
            params = msg.get("params", {})
            value = params.get("result", {})
            signature = value.get("signature", "")
            if signature:
                self._process_transaction(signature)

    def _process_transaction(self, signature):
        """
        For each new signature referencing the monitored wallets, fetch full tx and detect net token changes.
        """
        tx = self._get_transaction(signature)
        if not tx:
            return

        # For each wallet, compare old vs new balances => detect BUY/SELL
        for w in self.wallets:
            new_balances = self._fetch_token_balances(w)
            old_balances = self.balances_dict.get(w, {})

            self._detect_and_print_orders(w, old_balances, new_balances)

            # Update baseline
            self.balances_dict[w] = new_balances

    def _get_transaction(self, signature):
        """Fetch full transaction details, needed to confirm the event is relevant."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {"encoding":"jsonParsed"}
            ]
        }
        try:
            resp = requests.post(self.http_url, json=payload).json()
            return resp.get("result", None)
        except Exception as e:
            print(f"Error fetching transaction {signature}: {e}")
            return None

    def _detect_and_print_orders(self, wallet, old_balances, new_balances):
        """
        Compare old vs. new for each token. If new > old => BUY, if new < old => SELL.
        Print approximate USD value.
        """
        # Check tokens that remain or were newly minted
        for mint, new_amount in new_balances.items():
            old_amount = old_balances.get(mint, 0.0)
            delta = new_amount - old_amount
            if abs(delta) > 1e-9:  # significant change
                usd_value = self._get_usd_value(mint, abs(delta))
                if delta > 0:
                    # BUY
                    print(f"BUY ORDER: Wallet: {wallet}, Token: {mint}, Amount: {abs(delta):.4f}, USD: {usd_value:.2f}")
                else:
                    # SELL
                    print(f"SELL ORDER: Wallet: {wallet}, Token: {mint}, Amount: {abs(delta):.4f}, USD: {usd_value:.2f}")

        # Check tokens that disappeared (ex: old but not in new)
        for mint, old_amt in old_balances.items():
            if mint not in new_balances:
                # means new balance is 0
                usd_value = self._get_usd_value(mint, old_amt)
                print(f"SELL ORDER: Wallet: {wallet}, Token: {mint}, Amount: {old_amt:.4f}, USD: {usd_value:.2f}")

    def _get_usd_value(self, mint_address, token_amount):
        """
        Mock method to convert a (mint, amount) into approximate USD value.
        - Real code would do a token price lookup.
        """
        if mint_address == "So11111111111111111111111111111111111111112":  # Fake SOL mint
            return token_amount * 20.0
        else:
            return token_amount * 1.0

    def close(self):
        """Close the WebSocket cleanly."""
        if self.ws:
            self.ws.close()
            self.ws = None


if __name__ == "__main__":
    # 1) Load env vars
    API_KEY = os.environ.get("API_KEY")  # e.g. 72af8c8c-f916-4b84-a44d-5f0fb52765d6
    wallets_str = os.environ.get("WALLETS", "")  # Comma-separated
    WALLETS = [w.strip() for w in wallets_str.split(",") if w.strip()]

    if not API_KEY:
        print("Warning: No API_KEY found. Using a None key might cause 401 errors on Helius.")
    if not WALLETS:
        print("Warning: No WALLETS specified. Set WALLETS env var to a comma-separated list of addresses.")

    # 2) Construct Helius endpoints (or any other RPC you want)
    if API_KEY:
        HTTP_URL = f"https://api.helius.xyz/rpc?api-key={API_KEY}"
        WSS_URL = f"wss://rpc.helius.xyz/?api-key={API_KEY}"
    else:
        # Fallback if no key
        HTTP_URL = "https://api.mainnet-beta.solana.com"
        WSS_URL = "wss://api.mainnet-beta.solana.com"

    print("Using HTTP URL:", HTTP_URL)
    print("Using WSS  URL:", WSS_URL)
    print("Monitoring wallets:", WALLETS)

    monitor = SolanaWalletMonitor(http_url=HTTP_URL, wss_url=WSS_URL, wallets=WALLETS)
    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.close()
        print("Monitoring stopped.")
