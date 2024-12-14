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
def parse_notification(notification):
    """
    Example Message Format: "Wallet X bought Y tokens for $12,345"
    """
    match = re.search(r"Wallet (.+?) bought (.+?) tokens for \$(\d+,\d+)", notification)
    if match:
        wallet = match.group(1)
        token = match.group(2)
        amount_usd = float(match.group(3).replace(",", ""))
        return wallet, token, amount_usd
    return None

# Function to Trigger Hummingbot
def trigger_hummingbot(wallet, token, amount_usd):
    payload = {
        "wallet": wallet,
        "token": token,
        "amount_usd": amount_usd,
        "strategy": "whale_buy"
    }
    try:
        response = requests.post(HUMMINGBOT_API_URL, json=payload)
        if response.status_code == 200:
            print(f"Hummingbot triggered successfully for {token} (${amount_usd})")
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
    print(f"Message received: {message.content} in channel {message.channel.id}")
    

    # Respond to !ping command
    if message.channel.id == int(DISCORD_CHANNEL_ID):
        if message.content.strip() == "!ping":  # Match exact "!ping"
            await message.channel.send("Pong!")  #

    # Check if the message is in the specified channel
    if message.channel.id == DISCORD_CHANNEL_ID:
        details = parse_notification(message.content)
        if details:
            wallet, token, amount_usd = details
            if amount_usd >= 10000:  # Only trigger if the amount is $10,000 or more
                print(f"Whale Alert Detected: Wallet={wallet}, Token={token}, Amount=${amount_usd:.2f}")
                trigger_hummingbot(wallet, token, amount_usd)

# Run the Discord Bot
client.run(DISCORD_TOKEN)
