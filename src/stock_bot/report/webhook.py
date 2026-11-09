import json

import requests


class DiscordWebhook:
    def __init__(self, url):
        self.url = url

    def send(self, payload, chart, filename):
        try:
            response = requests.post(
                self.url,
                data={"payload_json": json.dumps(payload)},
                files={"file": (filename, chart, "image/png")},
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else None
            detail = f"（HTTP {status}）" if status is not None else ""
            raise RuntimeError(f"Discord webhook 發送失敗{detail}") from None
