import logging
import re
from threading import Lock
from time import monotonic

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)
CATALOG_URL = "https://isin.twse.com.tw/isin/C_public.jsp"
MARKET_MODES = {"TW": "2", "TWO": "4"}
REFRESH_INTERVAL = 24 * 60 * 60
RETRY_INTERVAL = 5 * 60
SECURITY_NAME = re.compile(r"([0-9]{4,6}[A-Z]?)\s+(.+)")


def parse_security_names(content):
    # The Chinese ISIN pages use Big5 and separate codes with a full-width space.
    page = BeautifulSoup(content, "html.parser", from_encoding="big5")
    names = {}
    for cell in page.select("tr > td:first-child"):
        match = SECURITY_NAME.fullmatch(cell.get_text(" ", strip=True))
        if match:
            code, name = match.groups()
            names[code] = name.strip()
    if not names:
        raise ValueError("證券名冊沒有可用的代碼與簡稱")
    return names


class TaiwanSecurityNames:
    def __init__(self):
        self.names = {}
        self.refresh_at = {}
        self.lock = Lock()

    def lookup(self, symbol, *, timeout=2):
        code, _, market = symbol.rpartition(".")
        mode = MARKET_MODES.get(market)
        if mode is None:
            return None
        if timeout <= 0 or not self.lock.acquire(blocking=False):
            return self.names.get(market, {}).get(code)
        try:
            if monotonic() >= self.refresh_at.get(market, 0):
                self.refresh(market, mode, timeout)
            return self.names.get(market, {}).get(code)
        finally:
            self.lock.release()

    def refresh(self, market, mode, timeout):
        try:
            response = requests.get(CATALOG_URL, params={"strMode": mode}, timeout=min(timeout, 2))
            response.raise_for_status()
            self.names[market] = parse_security_names(response.content)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("無法更新 %s 證券簡稱名冊：%s", market, exc)
            self.refresh_at[market] = monotonic() + RETRY_INTERVAL
        else:
            self.refresh_at[market] = monotonic() + REFRESH_INTERVAL


taiwan_security_names = TaiwanSecurityNames()
