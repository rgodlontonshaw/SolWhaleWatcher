# **Solana Whale and Market Analyzer**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square) ![Solana](https://img.shields.io/badge/Solana-Market%20Analyzer-orange?style=flat-square)

Solana Whale and Market Analyzer is a comprehensive tool designed to monitor wallet activities, track token transactions, and analyze potential investment opportunities in the Solana ecosystem. This tool leverages the **Helius API** to provide real-time insights into wallet activities, detect significant whale movements, and identify potential tokens worth investigating—all while sending notifications to **Discord**.

---

## **Features**
### 🔍 **Real-Time Wallet Monitoring**
- Track multiple Solana wallets for token transactions (buy/sell activity).
- Generate detailed insights on transaction percentages and wallet holdings.
- Alert when multiple wallets interact with the same token.

### 📊 **Token Analysis**
- Automatically analyze tokens with high activity from multiple wallets.
- Key metrics include:
  - **Total Supply**  
  - **Top Holder Distribution** (e.g., top 20 holders' percentage of supply)
  - **Suspicious Activity Detection** (e.g., concentration among top holders).

### 🐋 **Whale Activity Tracking**
- Detect whale-level transactions (high-value token buys or sells).
- Flag and report suspicious patterns, such as bulk movements.

### 📤 **Discord Notifications**
- Send real-time updates to a Discord channel using webhooks.
- Alerts include:
  - Whale activity detections.
  - Token analysis results for potential investments.

---

## **Setup**

### Prerequisites
- Python 3.9 or higher.
- A Solana RPC API Key (e.g., from Helius).
- A Discord Webhook URL for notifications.

### Installation
1. **Clone the Repository**
   ```bash
   git clone https://github.com/sn-i/solana-whale-and-market-analyzer.git
   cd solana-whale-and-market-analyzer
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**
   - Create a `.env` file in the project root and add the following:
     ```
     API_KEY=your_helius_api_key
     DISCORD_WEBHOOK_URL=your_discord_webhook_url
     WALLETS=wallet_address_1,wallet_address_2,...
     ```
   - Replace `your_helius_api_key` with your Helius API key.
   - Replace `your_discord_webhook_url` with your Discord webhook URL.
   - Replace `wallet_address_1,wallet_address_2,...` with the wallets you want to track.

---

## **Usage**

### Running the Application
Run the script to start monitoring wallets, tracking whale activities, and analyzing tokens.
```bash
python main.py
```

### Outputs
- **Console Logs**: Real-time wallet activity and whale detections.
- **Discord Alerts**: Notifications for whale movements and token analyses.

---

## **Project Structure**
```
solana-whale-and-market-analyzer/
├── checker.py           # Wallet monitoring logic
├── discord_notif.py     # Discord notification handler
├── token_checker.py     # Token analysis functionality
├── whale_tracker.py     # Whale activity tracking logic
├── main.py              # Entry point for the application
├── .env                 # Environment variables
├── requirements.txt     # Python dependencies
└── README.md            # Documentation
```

---

## **How It Works**

### Wallet Monitoring
1. Fetches token balances for tracked wallets using the Helius API.
2. Detects buy/sell transactions with details like old balance, new balance, and percentage change.
3. Alerts if more than 2 wallets interact with the same token.

### Token Analysis
1. Fetches token supply and holder distribution.
2. Flags tokens with:
   - High top-holder concentration (e.g., top 20 holders own >35% of supply).
   - Insufficient liquidity or trading volume.

### Whale Tracking
1. Analyzes recent transactions for high-value movements.
2. Detects whale transactions exceeding a threshold or significant percentage of the total supply.

---

## **Example Discord Alerts**

### Whale Activity Alert
```
⚠️ Whale Activity Detected:
- Token: GJAFwWjJ3vnTsrQVabjBVK2TYB1YtRCQXRDfDgUnpump
- Transaction: TxnID123456789
- Amount: 100,000.00
```

### Token Analysis Alert
```
🚨 Token Analysis for DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263:
Status: Potentially Good
Reason: Token meets decentralization criteria.
Total Supply: 1,000,000.00
Top Holders' Ownership: 28.5%
Top Holders:
- Address: Holder1, Balance: 100,000.00
- Address: Holder2, Balance: 90,000.00
```

---

## **Contributing**
Contributions are welcome! If you have suggestions, feel free to open an issue or submit a pull request.
