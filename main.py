import discord
import re
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))  # Ensure this is an integer
HUMMINGBOT_API_URL = "http://localhost:9000/api/trigger-strategy"  # Adjust as needed

# Discord Client with Intents
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)


# Function to Parse Whale Alert Notifications
# Function to Parse Whale Alert Notifications
def parse_notification(notification):
    """
    Example Message Format from Screenshot:
    "From: 90.736 SOL ($19,768.94) To: 186.58K LUCE ($19,954.50) @ $0.11"
    """
    match = re.search(
        r"From: ([\d.]+) SOL \(\$([\d,]+.\d+)\) To: ([\d.]+[A-Za-z]*) (\w+) \(\$([\d,]+.\d+)\) @ \$(\d+\.\d+)",
        notification
    )
    if match:
        sol_amount = float(match.group(1))
        sol_usd = float(match.group(2).replace(",", ""))
        token_amount = match.group(3)
        token_symbol = match.group(4)
        token_usd = float(match.group(5).replace(",", ""))
        token_price = float(match.group(6))
        return sol_amount, sol_usd, token_amount, token_symbol, token_usd, token_price
    return None

# Function to Trigger Hummingbot
def trigger_hummingbot(sol_amount, sol_usd, token_amount, token_symbol, token_usd, token_price):
    payload = {
        "sol_amount": sol_amount,
        "sol_usd": sol_usd,
        "token_amount": token_amount,
        "token_symbol": token_symbol,
        "token_usd": token_usd,
        "token_price": token_price,
        "strategy": "whale_buy"
    }
    try:
        response = requests.post(HUMMINGBOT_API_URL, json=payload)
        if response.status_code == 200:
            print(f"Hummingbot triggered successfully for {token_symbol} (${token_usd})")
        else:
            print(f"Failed to trigger Hummingbot: {response.text}")
    except Exception as e:
        print(f"Error triggering Hummingbot: {e}")

# Event Listener for Bot Startup
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

# Event Listener for Discord Messages
@client.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == client.user:
        return

    # Debugging: Log received messages
    if message.embeds:
        for embed in message.embeds:
            print(f"Embed details: {embed.to_dict()}")  # Convert embed to dictionary for better logging
    else:
        print("No embeds found in the message.")
    print(f"Message received: {message.content} in channel {message.channel.id}")
    
    


    # Check if the message is in the specified channel
    if message.channel.id == DISCORD_CHANNEL_ID:
        # Handle plain text messages
        if message.content.strip():
            details = parse_notification(message.content)
            if details:
                process_notification(details)

        # Handle embedded content
        if message.embeds:
            for embed in message.embeds:
                embed_data = embed.to_dict()  # Extract full embed as a dictionary
                
                from_field = None
                to_field = None

                # Extract 'From' and 'To' fields
                for field in embed_data.get("fields", []):
                    if field["name"] == "From":
                        from_field = field["value"]
                    elif field["name"] == "To":
                        to_field = field["value"]

                if from_field and to_field:
                    print(f"Parsing From: {from_field}, To: {to_field}")
                    details = parse_fields(from_field, to_field)
                    if details:
                        process_notification(details)
                        
    def parse_fields(from_field, to_field):
        """
        Parses 'From' and 'To' fields to extract amounts, token names, and USD values.
        
        Example 'From' field:
            "58.45K [Fartcoin] ($35,179.10) @ $0.60"
        Example 'To' field:
            "<:solana:12345> 158.84 [SOL] ($34,731.74)"
        """
        # Regular expression to match: amount, token name, and USD value
        pattern = r"([\d,.]+[KMB]*) \[(\w+)\] \(\$(\d+,\d+\.\d+)\)"
        
        from_match = re.search(pattern, from_field)
        to_match = re.search(pattern, to_field)
        
        if from_match and to_match:
            # Extract "From" details
            from_amount = convert_to_number(from_match.group(1))
            from_token = from_match.group(2)
            from_usd = float(from_match.group(3).replace(",", ""))
            
            # Extract "To" details
            to_amount = convert_to_number(to_match.group(1))
            to_token = to_match.group(2)
            to_usd = float(to_match.group(3).replace(",", ""))
            
            return from_amount, from_token, from_usd, to_amount, to_token, to_usd
        
        return None

def convert_to_number(amount_str):
    """
    Converts amounts like '58.45K' to 58450.
    Supports K (thousand), M (million), and B (billion).
    """
    amount_str = amount_str.replace(",", "")
    if "K" in amount_str:
        return float(amount_str.replace("K", "")) * 1_000
    elif "M" in amount_str:
        return float(amount_str.replace("M", "")) * 1_000_000
    elif "B" in amount_str:
        return float(amount_str.replace("B", "")) * 1_000_000_000
    return float(amount_str)


def process_notification(details):
    """
    Handle notification details after parsing.
    """
    sol_amount, sol_usd, token_amount, token_symbol, token_usd, token_price = details
    if token_usd >= 10000:  # Example condition
        print(f"Whale Alert Detected: SOL={sol_amount}, Token={token_symbol}, Amount=${token_usd:.2f}")
        trigger_hummingbot(sol_amount, sol_usd, token_amount, token_symbol, token_usd, token_price)

# Run the Discord Bot
client.run(DISCORD_TOKEN)
