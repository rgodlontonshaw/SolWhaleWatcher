import os
import time
import requests
from collections import defaultdict

TIME_WINDOW_SECONDS = 30000  # Only consider transactions from the last 5 minutes

# ------------------ ENV/CONFIG ------------------
API_KEY = os.environ.get("API_KEY")  # e.g. '72af8c8c-f916-4b84-a44d-5f0fb52765d6'
WALLETS_STR = os.environ.get("WALLETS", "")
WALLETS = [w.strip() for w in WALLETS_STR.split(",") if w.strip()]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

if not WALLETS:
    # Fallback wallet if none provided
    WALLETS = ["D4zVhwuUsFbcaty7wJhNEZ7VEwPHXQ5d2heXPxM5yWhL"]

# Decide on the RPC endpoint (Helius vs. Solana)
if API_KEY:
    HTTP_URL = f"https://api.helius.xyz/rpc?api-key={API_KEY}"
else:
    HTTP_URL = "https://api.mainnet-beta.solana.com"

print("HTTP_URL:", HTTP_URL)
print("Polling wallets for recent BUYs (within 5 min):", WALLETS)
print("Discord Webhook URL:", DISCORD_WEBHOOK_URL if DISCORD_WEBHOOK_URL else "No Webhook set")

# ------------------ DISCORD NOTIFIER ------------------
class DiscordNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_notifications(self, message):
        if not self.webhook_url:
            print("(No Discord Webhook set) ->", message)
            return
        data = {"content": message}
        try:
            resp = requests.post(self.webhook_url, json=data)
            if resp.status_code >= 300:
                print(f"Discord notification failed [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print("Discord notification error:", e)

discord_notifier = DiscordNotifier(DISCORD_WEBHOOK_URL)

# ------------------ HUMMINGBOT TRIGGER ------------------
def hummingbot_trigger(wallet, mint, usd_value):
    """
    If a net inflow (buy) is >= $10,000, we 'trigger' Hummingbot logic here.
    """
    print(f"HUMMINGBOT TRIGGER: Whale Buy > $10,000! Wallet={wallet}, Mint={mint}, USD={usd_value:.2f}")
    # In a real setup:
    # requests.post(HUMMINGBOT_URL, json={...})

# ------------------ PRICE LOGIC ------------------
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
    If it's the SOL mint, fetch Coingecko price every 30s. 
    Otherwise fallback to $1 each.
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

# ------------------ RPC CALLS ------------------
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
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [signature, {"encoding":"jsonParsed"}]
    }
    resp = requests.post(HTTP_URL, json=payload).json()
    return resp.get("result")

def fetch_token_balances(wallet):
    """
    Return {mint: ui_amount} for all SPL tokens the wallet currently holds.
    This automatically picks up new tokens each iteration if the wallet acquires them.
    """
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

# ------------------ BUY HANDLING & MULTI-WALLET ALERT ------------------
def detect_buy_and_record(wallet, mint, delta_amount, timestamp_str, transaction_records):
    """
    If net inflow > 0, print a BUY. If >= $10k => trigger Hummingbot & Discord.
    Also record in transaction_records for multi-wallet detection.
    """
    usd_value = _get_usd_value(mint, delta_amount)

    message = (f"[{timestamp_str}] BUY: Wallet={wallet}, Mint={mint}, "
               f"Amount={delta_amount:.4f}, USD={usd_value:.2f}")
    print(message)

    # Discord: any BUY event
    discord_notifier.send_notifications(message)

    # Whale check
    if usd_value >= 10000:
        whale_msg = f"**WHALE BUY ALERT** >= $10k\n{message}"
        discord_notifier.send_notifications(whale_msg)
        hummingbot_trigger(wallet, mint, usd_value)
        print(whale_msg)

    transaction_records["buy"][mint].append(wallet)

def check_common_transactions(transaction_records):
    """
    If more than 2 distinct wallets bought the same token this cycle => multi-wallet Discord alert.
    """
    for action in ["buy", "sell"]:
        for token, wallet_list in transaction_records[action].items():
            if len(wallet_list) > 2:
                action_message = "bought" if action == "buy" else "sold"
                wallets_involved = ", ".join(wallet_list)
                alert_msg = (f"ALERT: More than 2 wallets {action_message} token {token} in this cycle!\n"
                             f"Wallets: {wallets_involved}")
                print(alert_msg)
                discord_notifier.send_notifications(alert_msg)
                
def fetch_token_accounts_for_owner(wallet):
    """
    Returns a list of token account addresses (pubkeys) owned by 'wallet'.
    Essentially a slightly modified version of 'fetch_token_balances' 
    that collects token account pubkeys instead of building a mint->balance dict.
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
        resp = requests.post(HTTP_URL, json=payload).json()
        accounts = resp.get("result", {}).get("value", [])
        token_account_addresses = []
        for acct in accounts:
            token_account_pubkey = acct["pubkey"]
            token_account_addresses.append(token_account_pubkey)
        return token_account_addresses
    except Exception as e:
        print(f"Error fetching token accounts for {wallet}: {e}")
        return []


# ------------------ MAIN LOOP ------------------
def run_script():
    known_signatures = set()
    balances_dict = {}
    transaction_records = {
        "buy": defaultdict(list),
        "sell": defaultdict(list),
    }

    # 1) Init baseline balances
    for w in WALLETS:
        print(f"Fetching initial balances for wallet: {w}")
        balances_dict[w] = fetch_token_balances(w)
        print(f"Initial balances for {w}: {balances_dict[w]}")

    print(f"Starting polling loop every 5 seconds (only new transactions <= {TIME_WINDOW_SECONDS//60} min old)...")

    while True:
        try:
            # Clear transaction records each iteration
            transaction_records["buy"].clear()
            transaction_records["sell"].clear()

            current_unix_time = time.time()

            for wallet in WALLETS:
                # 1) Fetch all token accounts for this wallet
                print(f"Fetching token accounts for wallet: {wallet}")
                token_accounts = fetch_token_accounts_for_owner(wallet)  # returns a list of token account addresses
                print(f"Token accounts for {wallet}: {token_accounts}")

                for ta_addr in token_accounts:
                    # 2) Poll new signatures for each token account
                    print(f"Fetching signatures for token account: {ta_addr}")
                    sigs = get_signatures_for_address(ta_addr, limit=10)
                    print(f"Signatures for {ta_addr}: {sigs}")

                    for sig_info in sigs:
                        signature = sig_info["signature"]
                        block_time = sig_info.get("blockTime", 0)
                        if not block_time:
                            print(f"Skipping signature {signature} (no blockTime)")
                            continue

                        if block_time < current_unix_time - TIME_WINDOW_SECONDS:
                            print(f"Skipping signature {signature} (older than time window)")
                            continue

                        if signature not in known_signatures:
                            print(f"Processing new signature: {signature}")
                            known_signatures.add(signature)
                            tx_details = get_transaction(signature)
                            print(f"Transaction details for {signature}: {tx_details}")

                            if tx_details:
                                timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(block_time))
                                old_bal = balances_dict.get(wallet, {})
                                new_bal = fetch_token_balances(wallet)

                                # Detect net inflows
                                for mint, new_amt in new_bal.items():
                                    old_amt = old_bal.get(mint, 0.0)
                                    delta = new_amt - old_amt
                                    if delta > 1e-9:
                                        detect_buy_and_record(wallet, mint, delta, timestamp_str, transaction_records)

                                # Update stored balances
                                balances_dict[wallet] = new_bal

            # Multi-wallet check
            check_common_transactions(transaction_records)

            time.sleep(5)

        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as e:
            print("Error in main loop:", e)
            # If connection or parse error, wait & retry
            time.sleep(5)


        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as e:
            print("Error in main loop:", e)
            # If connection or parse error, wait & retry
            time.sleep(5)

def main():
    """
    Outer loop that re-runs `run_script()` if a fatal error occurs 
    (e.g. internet cut off), so script doesn't fully exit.
    """
    while True:
        try:
            run_script()
            break  # If run_script completes gracefully, exit the loop.
        except KeyboardInterrupt:
            print("User interrupted; exiting outer loop.")
            break
        except Exception as e:
            print("Fatal error, retry in 10s:", e)
            time.sleep(10)
            # Loop re-runs run_script()

if __name__ == "__main__":
    main()
