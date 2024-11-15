import requests


class DiscordNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_notification(self, message):
        try:
            payload = {"content": message}
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            print("Discord notification sent!")
        except requests.exceptions.RequestException as e:
            print(f"Error sending Discord notification: {str(e)}")
