# -*- coding: utf-8 -*-
"""
Dollar Price Checker - Cloud Version (GitHub Actions)
Uses bonbast.com API for accurate free market prices.
Sends notifications via Telegram only (no Windows toast).
"""

import requests
import json
import re
import os
import sys
import time
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# === CONFIG (from GitHub Secrets) ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7902915191:AAFi7N7WZB-dD5IXQo6IqoVBaEM8RBv7erE")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@robomohsen")


def fetch_bonbast_prices():
    """Fetch free market prices from bonbast.com using session + AJAX."""
    for attempt in range(3):
        try:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            })
            s.verify = False

            r = s.get("https://www.bonbast.com/", timeout=30)
            r.raise_for_status()
            time.sleep(1)

            m = re.search(r'param:\s*"([^"]+)"', r.text)
            if not m:
                raise Exception("Could not extract param from bonbast.com")
            param = m.group(1)

            r2 = s.post(
                "https://www.bonbast.com/json",
                data={"param": param},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.bonbast.com/",
                },
                timeout=30,
            )
            data = r2.json()

            if "reset" in data:
                raise Exception("Session expired, retry needed")

            return data
        except Exception as e:
            if attempt < 2:
                print(f"  Attempt {attempt+1} failed: {e}. Retrying in 3s...")
                time.sleep(3)
            else:
                raise


def fmt(n):
    """Format number with comma separators."""
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def send_telegram(text):
    """Send message to Telegram."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text},
            timeout=15,
        )
        result = resp.json()
        if result.get("ok"):
            return True
        else:
            print(f"Telegram API error: {result}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return False


def main():
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")

    print(f"[{date_str}] Fetching prices from bonbast.com...")

    try:
        data = fetch_bonbast_prices()
    except Exception as e:
        print(f"[{date_str}] ERROR: {e}", file=sys.stderr)
        return

    # Extract prices
    usd_sell = int(data.get("usd1", 0))
    usd_buy = int(data.get("usd2", 0))
    gold = int(data.get("gol18", 0))
    azadi = int(data.get("azadi1", 0))
    nim = int(data.get("azadi1_2", 0))
    emami = int(data.get("emami1", 0))
    btc_usd = float(data.get("bitcoin", 0))
    btc_toman = round(btc_usd * usd_sell)
    bourse = float(data.get("bourse", 0))
    ounce_usd = float(data.get("ounce", 0))
    ounce_toman = round(ounce_usd * usd_sell)
    last_modified = data.get("last_modified", date_str)

    # Build Telegram message
    msg = f"📊 قیمت لحظه‌ای بازار آزاد\n\n"
    msg += f"🕐 بروزرسانی: {last_modified}\n\n"
    msg += f"💵 دلار:\n"
    msg += f"   فروش: {fmt(usd_sell)} تومان\n"
    msg += f"   خرید: {fmt(usd_buy)} تومان\n\n"
    msg += f"🥇 طلا (۱۸ عیار): {fmt(gold)} تومان/گرم\n"
    msg += f"🥇 انس طلا: ${fmt(ounce_usd)}\n"
    msg += f"   = {fmt(ounce_toman)} تومان\n\n"
    msg += f"🪙 سکه:\n"
    msg += f"   آزادی: {fmt(azadi)} تومان\n"
    msg += f"   نیم: {fmt(nim)} تومان\n"
    msg += f"   امامی: {fmt(emami)} تومان\n\n"
    msg += f"₿ بیتکوین: ${fmt(btc_usd)}\n"
    msg += f"   = {fmt(btc_toman)} تومان\n\n"
    msg += f"💰 تتر (USDT): {fmt(usd_sell)} تومان\n\n"
    msg += f"📈 شاخص بورس: {fmt(bourse)}"

    print(f"[{date_str}] USD:{fmt(usd_sell)}/{fmt(usd_buy)} | Gold:{fmt(gold)} | BTC:${fmt(btc_usd)} | Bourse:{fmt(bourse)}")

    # Send Telegram
    tg_ok = send_telegram(msg)
    if tg_ok:
        print(f"[{date_str}] Telegram sent OK")
    else:
        print(f"[{date_str}] Telegram FAILED")
        sys.exit(1)

    print(f"[{date_str}] Done!")


if __name__ == "__main__":
    main()
