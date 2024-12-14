import os
import time
import requests
from collections import defaultdict

TIME_WINDOW_SECONDS = 300  # Only consider transactions from the last 5 minutes

# -------------- CONFIG & ENV --------------

API_KEY = os.environ.get("API_KEY")  # e.g. '72af8c8c-f916-4b84-a44d-5f0fb52765d6'
WALLETS_STR = os.environ.get("WALLETS", "")
WALLETS = [w.strip() for w in WALLETS_STR.split(",") if w.strip()]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

if not WALLETS:
    WALLETS = ["D4zVhwuUsFbcaty7wJhNEZ7VEwPHXQ5d2heXPxM5yWhL"]  # fallback

if API_KEY:
    HTTP_URL = f"https://api.helius.xyz/rpc?api-key={API_KEY}"
else:
    HTTP_URL = "https://api.mainnet-beta.solana.com"

print("HTTP_URL:", HTTP_URL)
print("Polling wallets for recent BUYs (within 5 min):", WALLETS)
print("Discord Webhook URL:", DISCORD_WEBHOOK_URL if DISCORD_WEBHOOK_URL else "No Webhook set")

# -------------- DISCORD NOTIFIER --------------

class DiscordNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_notifications(self, message):
        """Simple text message to Discord webhook."""
        if not self.webhook_url:
            print("No Discord Webhook URL set; skipping Discord notification.")
            return
        data = {"content": message}
        try:
            resp = requests.post(self.webhook_url, json=data)
            if resp.status_code >= 300:
                print(f"Discord notification failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            print("Discord notification error:", e)

discord_notifier = DiscordNotifier(DISCORD_WEBHOOK_URL)

# -------------- PRICE LOGIC --------------

price_cache = {}
last_price_fetch_ts = 0

def get_coingecko_price(symbol: str):
    if symbol == "sol":
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
            data = r.json()
            return data["solana"]["usd"]
        except:
            return None
    return None

def _get_usd_value(mint_address, amount):
    """
    Convert token mint & amount => approx USD.
    """
    global price_cache, last_price_fetch_ts
    SOL_MINT = "So11111111111111111111111111111111111111112"
    current_time = time.time()

    if mint_address == SOL_MINT:
        if "sol" not in price_cache or (current_time - last_price_fetch_ts) > 30:
            sol_price = get_coingecko_price("sol")
            if sol_price:
                price_cache["sol"] = sol_price
            last_price_fetch_ts = current_time
        sol_price = price_cache.get("sol", 20.0)
        return amount * sol_price
    else:
        return amount * 1.0

# -------------- RPC CALLS --------------

def get_signatures_for_address(wallet, limit=10):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [wallet, {"limit": limit}]
    }
    resp = requests.post(HTTP_URL, json=payload).json()
    return resp.get("result", [])

def get_transaction(signature):
    payload = {
        "jsonrpc":"2.0",
        "id":1,
        "method":"getTransaction",
        "params":[signature, {"encoding":"jsonParsed"}]
    }
    resp = requests.post(HTTP_URL, json=payload).json()
    return resp.get("result")

def fetch_token_balances(wallet):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {"programId":"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding":"jsonParsed"}
        ]
    }
    resp = requests.post(HTTP_URL, json=payload).json()
    val = resp.get("result", {}).get("value", [])
    token_dict = {}
    for acct in val:
        info = acct["account"]["data"]["parsed"]["info"]
        mint = info["mint"]
        amount_str = info["tokenAmount"]["amount"]
        decimals = info["tokenAmount"]["decimals"]
        ui_amount = float(amount_str) / (10**decimals)
        token_dict[mint] = ui_amount
    return token_dict

# -------------- BUY DETECTION & MULTI-WALLET ALERT --------------

def detect_buy_and_record(wallet, mint, delta_amount, timestamp_str, transaction_records):
    """We found a net inflow (BUY). Save it in transaction_records & print."""
    usd_value = _get_usd_value(mint, delta_amount)
    print(f"[{timestamp_str}] BUY: Wallet={wallet}, Mint={mint}, Amount={delta_amount:.4f}, USD={usd_value:.2f}")

    # Record the buy in transaction_records for multi-wallet detection
    transaction_records["buy"][mint].append(wallet)

def check_common_transactions(transaction_records):
    """
    If more than 2 wallets bought the same token in this cycle => Discord alert
    """
    for action in ["buy", "sell"]:
        for token, wallet_list in transaction_records[action].items():
            if len(wallet_list) > 2:
                action_message = "bought" if action == "buy" else "sold"
                wallets_involved = ", ".join(wallet_list)
                message = (
                    f"ALERT: More than 2 wallets {action_message} token {token}!\n"
                    f"Wallets: {wallets_involved}"
                )
                print(message)
                discord_notifier.send_notifications(message)

# -------------- MAIN LOOP --------------

def main():
    known_signatures = set()
    balances_dict = {}  # { wallet: {mint: amount}}
    transaction_records = {
        "buy": defaultdict(list),
        "sell": defaultdict(list),
    }

    # Initialize baseline balances
    for w in WALLETS:
        balances_dict[w] = fetch_token_balances(w)

    print("Starting polling loop every 5 seconds...only recent transactions (<5 mins).")

    while True:
        try:
            # Clear transaction records each iteration
            transaction_records["buy"].clear()
            transaction_records["sell"].clear()

            current_unix_time = time.time()

            for wallet in WALLETS:
                sigs = get_signatures_for_address(wallet, limit=10)
                for sig_info in sigs:
                    signature = sig_info["signature"]
                    block_time = sig_info.get("blockTime", 0)  # epoch seconds
                    if not block_time:
                        # If blockTime is None or 0, might be incomplete info
                        continue

                    # Skip old transactions
                    if block_time < current_unix_time - TIME_WINDOW_SECONDS:
                        # older than 5 minutes, skip
                        continue

                    if signature not in known_signatures:
                        known_signatures.add(signature)
                        tx_details = get_transaction(signature)
                        if tx_details:
                            # Create a human-readable timestamp
                            timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(block_time))
                            old_bal = balances_dict.get(wallet, {})
                            new_bal = fetch_token_balances(wallet)

                            # Detect net inflows
                            for mint, new_amt in new_bal.items():
                                old_amt = old_bal.get(mint, 0.0)
                                delta = new_amt - old_amt
                                if delta > 1e-9:  # net positive => BUY
                                    detect_buy_and_record(wallet, mint, delta, timestamp_str, transaction_records)

                            # Update baseline
                            balances_dict[wallet] = new_bal

            # Check if multiple wallets bought the same token
            check_common_transactions(transaction_records)

            time.sleep(5)

        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as e:
            print("Error in main loop:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
