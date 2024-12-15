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
def trigger_hummingbot(from_amount, from_usd, to_amount, to_token, to_usd):
    """
    Sends a request to Hummingbot with transaction details.
    """
    payload = {
        "from_amount": from_amount,
        "from_usd": from_usd,
        "to_amount": to_amount,
        "to_token": to_token,
        "to_usd": to_usd,
        "strategy": "whale_buy"
    }

    try:
        response = requests.post("http://localhost:9000/api/trigger-strategy", json=payload)
        if response.status_code == 200:
            print(f"✅ Hummingbot triggered successfully for {to_token} (${to_usd:.2f})")
        else:
            print(f"❌ Failed to trigger Hummingbot: {response.text}")
    except Exception as e:
        print(f"⚠️ Error triggering Hummingbot: {e}")


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

    # # Debugging: Log received messages
    # if message.embeds:
    #     for embed in message.embeds:
    #         print(f"Embed details: {embed.to_dict()}")  # Convert embed to dictionary for better logging
    # else:
    #     print("No embeds found in the message.")
    # print(f"Message received: {message.content} in channel {message.channel.id}")
    
    


    # Check if the message is in the specified channel
    if message.channel.id == DISCORD_CHANNEL_ID:
        # Handle plain text messages
        if message.content.strip():
            details = parse_notification(message.content)
            if details:
                process_notification(details)

    if message.embeds:
        for embed in message.embeds:
            embed_data = embed.to_dict()  # Convert embed to dictionary
            
            from_field = None
            to_field = None

            # Extract "From" and "To" fields
            for field in embed_data.get("fields", []):
                if field["name"] == "From":
                    from_field = field["value"]
                elif field["name"] == "To":
                    to_field = field["value"]
            
            # Parse fields if both exist
            # Parse fields if both "From" and "To" exist
        if from_field and to_field:
            print(f"Parsing From: {from_field}, To: {to_field}")
            details = parse_fields(from_field, to_field)
            print(f"Parsed details: {details}")  # Debug the output
            if details:
                process_notification(details)
            else:
                print("⚠️ Failed to parse fields. Check field format or regex.")

                    
                        
def parse_fields(from_field, to_field):
    """
    Parses 'From' and 'To' fields to extract amounts, token names, and USD values.
    Handles optional emoji prefixes, URLs, and additional parts like '@ $0.00'.
    """
    # Enhanced regex to handle edge cases
    pattern = r"(?:<:\w+:\d+>\s*)?([\d,.]+[KMB]*)\s+\[([^\]]+)\]\(https?:\/\/[^\)]+\)\s+\(\$(\d+(?:,\d{3})*\.\d+|0\.00)\)(?: @ \$[\d,.]+)?"
    
    from_match = re.search(pattern, from_field)
    to_match = re.search(pattern, to_field)
    
    print(f"Debug From: {from_field}, Match: {from_match}")
    print(f"Debug To: {to_field}, Match: {to_match}")

    if from_match and to_match:
        from_amount = convert_to_number(from_match.group(1))
        from_token = from_match.group(2).strip()
        from_usd = float(from_match.group(3).replace(",", ""))
        
        to_amount = convert_to_number(to_match.group(1))
        to_token = to_match.group(2).strip()
        to_usd = float(to_match.group(3).replace(",", ""))
        
        return from_amount, from_token, from_usd, to_amount, to_token, to_usd
    
    print("⚠️ No match found!")
    return None


def convert_to_number(amount_str):
    """
    Converts amounts like '1.91M' to 1910000.
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
    Handle parsed details from 'From' and 'To' fields.
    """
    from_amount, from_token, from_usd, to_amount, to_token, to_usd = details
    print(f"\n🔄 Swap Detected:")
    print(f"   From: {from_amount} {from_token} (${from_usd:.2f})")
    print(f"   To:   {to_amount} {to_token} (${to_usd:.2f})")

    # Trigger Hummingbot for transactions with a value > $1000
    if from_usd >= 10000 or to_usd >= 10000:
        print("🚨 High-value transaction detected! Triggering Hummingbot...")
        trigger_hummingbot(from_amount, from_usd, to_amount, to_token, to_usd)
    else:
        print("ℹ️ Transaction value below threshold, Hummingbot not triggered.")


# Run the Discord Bot
client.run(DISCORD_TOKEN)
