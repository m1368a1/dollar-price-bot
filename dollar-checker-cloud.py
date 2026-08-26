# -*- coding: utf-8 -*-
"""
Smart Financial Bot - Iran Market Analysis
Features:
  1. Real-time prices from bonbast.com (dollar, gold, coins, crypto, bourse)
  2. Fear & Greed Index (global crypto sentiment)
  3. Global market data (BTC dominance, trending coins, market cap)
  4. Whale tracker (large unconfirmed BTC transactions)
  5. Iran vs Global price comparison
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

# === CONFIG ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7902915191:AAFi7N7WZB-dD5IXQo6IqoVBaEM8RBv7erE")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@robomohsen")


# ============================================================
#  SECTION 1: Iran Market Prices (bonbast.com)
# ============================================================
def fetch_bonbast_prices():
    """Fetch free market prices from bonbast.com."""
    for attempt in range(3):
        try:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            s.verify = False
            r = s.get("https://www.bonbast.com/", timeout=30)
            r.raise_for_status()
            time.sleep(1)
            m = re.search(r'param:\s*"([^"]+)"', r.text)
            if not m:
                raise Exception("Could not extract param")
            r2 = s.post("https://www.bonbast.com/json", data={"param": m.group(1)},
                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://www.bonbast.com/"}, timeout=30)
            data = r2.json()
            if "reset" in data:
                raise Exception("Session expired")
            return data
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                raise


# ============================================================
#  SECTION 2: Fear & Greed Index
# ============================================================
def fetch_fear_greed():
    """Fetch crypto Fear & Greed Index from alternative.me."""
    try:
        s = requests.Session()
        s.verify = False
        r = s.get("https://api.alternative.me/fng/?limit=7", timeout=15)
        data = r.json()["data"]
        current = data[0]
        value = int(current["value"])
        classification = current["value_classification"]

        # Emoji based on value
        if value <= 20:
            emoji = "😱"
        elif value <= 40:
            emoji = "😰"
        elif value <= 60:
            emoji = "😐"
        elif value <= 80:
            emoji = "😏"
        else:
            emoji = "🤑"

        # 7-day trend
        values_7d = [int(d["value"]) for d in data]
        avg_7d = sum(values_7d) // len(values_7d)
        trend = "📈" if values_7d[0] > values_7d[-1] else "📉" if values_7d[0] < values_7d[-1] else "➡️"

        return {
            "value": value,
            "emoji": emoji,
            "classification": classification,
            "avg_7d": avg_7d,
            "trend": trend,
            "history": values_7d,
        }
    except Exception as e:
        print(f"  F&G error: {e}", file=sys.stderr)
        return None


# ============================================================
#  SECTION 3: Global Market Data (CoinGecko)
# ============================================================
def fetch_global_market():
    """Fetch global crypto market data from CoinGecko."""
    try:
        s = requests.Session()
        s.verify = False
        # Global data
        r = s.get("https://api.coingecko.com/api/v3/global", timeout=15)
        g = r.json()["data"]

        # Trending
        r2 = s.get("https://api.coingecko.com/api/v3/search/trending", timeout=15)
        trending = r2.json()["coins"][:5]

        # Top coins by price change
        r3 = s.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false&price_change_percentage=24h", timeout=15)
        top_coins = r3.json()

        return {
            "btc_dominance": round(g["market_cap_percentage"]["btc"], 1),
            "total_market_cap_t": round(g["total_market_cap"]["usd"] / 1e12, 2),
            "total_volume_t": round(g["total_volume"]["usd"] / 1e12, 2),
            "market_cap_change_24h": round(g["market_cap_change_percentage_24h_usd"], 2),
            "trending": [(c["item"]["name"], c["item"]["symbol"], c["item"].get("market_cap_rank", "?")) for c in trending],
            "top_gainers": [(c["name"], c["symbol"], c.get("price_change_percentage_24h", 0) or 0) for c in top_coins if (c.get("price_change_percentage_24h", 0) or 0) > 0][:3],
            "top_losers": [(c["name"], c["symbol"], c.get("price_change_percentage_24h", 0) or 0) for c in top_coins if (c.get("price_change_percentage_24h", 0) or 0) < 0][:3],
        }
    except Exception as e:
        print(f"  CoinGecko error: {e}", file=sys.stderr)
        return None


# ============================================================
#  SECTION 4: Whale Tracker (blockchain.info)
# ============================================================
def fetch_whale_alerts():
    """Track large unconfirmed BTC transactions."""
    try:
        s = requests.Session()
        s.verify = False
        r = s.get("https://blockchain.info/unconfirmed-transactions?format=json", timeout=15)
        txs = r.json()["txs"]

        whales = []
        for t in txs:
            out_value = sum(o.get("value", 0) for o in t.get("out", [])) / 1e8
            if out_value >= 100:  # >= 100 BTC
                whales.append({
                    "hash": t["hash"][:16] + "...",
                    "btc": round(out_value, 2),
                    "usd": round(out_value * 80000, 0),  # approximate
                })

        # Sort by value
        whales.sort(key=lambda x: x["btc"], reverse=True)

        return {
            "total_unconfirmed": len(txs),
            "whales": whales[:5],  # Top 5 whale txs
            "total_whale_btc": round(sum(w["btc"] for w in whales), 2),
        }
    except Exception as e:
        print(f"  Whale error: {e}", file=sys.stderr)
        return None


# ============================================================
#  HELPER FUNCTIONS
# ============================================================
def fmt(n):
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def send_telegram(text):
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
            print(f"Telegram error: {result}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return False


# ============================================================
#  MAIN
# ============================================================
def main():
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")

    print(f"[{date_str}] Fetching all data...")

    # Fetch all data
    bonbast = None
    fear_greed = None
    global_market = None
    whales = None

    errors = []

    try:
        bonbast = fetch_bonbast_prices()
        print("  [OK] Bonbast prices")
    except Exception as e:
        errors.append(f"Bonbast: {e}")
        print(f"  [ERR] Bonbast: {e}")

    try:
        fear_greed = fetch_fear_greed()
        print("  [OK] Fear & Greed")
    except Exception as e:
        errors.append(f"F&G: {e}")
        print(f"  [ERR] Fear & Greed: {e}")

    try:
        global_market = fetch_global_market()
        print("  [OK] Global market")
    except Exception as e:
        errors.append(f"Global: {e}")
        print(f"  [ERR] Global market: {e}")

    try:
        whales = fetch_whale_alerts()
        print("  [OK] Whale tracker")
    except Exception as e:
        errors.append(f"Whale: {e}")
        print(f"  [ERR] Whale: {e}")

    if not bonbast:
        print(f"[{date_str}] FATAL: No bonbast data. Aborting.")
        return

    # Extract Iran prices
    usd_sell = int(bonbast.get("usd1", 0))
    usd_buy = int(bonbast.get("usd2", 0))
    gold = int(bonbast.get("gol18", 0))
    azadi = int(bonbast.get("azadi1", 0))
    nim = int(bonbast.get("azadi1_2", 0))
    emami = int(bonbast.get("emami1", 0))
    btc_usd = float(bonbast.get("bitcoin", 0))
    btc_toman = round(btc_usd * usd_sell)
    bourse = float(bonbast.get("bourse", 0))
    ounce_usd = float(bonbast.get("ounce", 0))
    ounce_toman = round(ounce_usd * usd_sell)
    last_modified = bonbast.get("last_modified", date_str)

    # ============================================================
    #  BUILD MESSAGE 1: Iran Market Prices
    # ============================================================
    msg1 = f"📊 قیمت لحظه‌ای بازار آزاد\n\n"
    msg1 += f"🕐 بروزرسانی: {last_modified}\n\n"
    msg1 += f"💵 دلار:\n"
    msg1 += f"   فروش: {fmt(usd_sell)} تومان\n"
    msg1 += f"   خرید: {fmt(usd_buy)} تومان\n\n"
    msg1 += f"🥇 طلا (۱۸ عیار): {fmt(gold)} تومان/گرم\n"
    msg1 += f"🥇 انس طلا: ${fmt(ounce_usd)}\n"
    msg1 += f"   = {fmt(ounce_toman)} تومان\n\n"
    msg1 += f"🪙 سکه:\n"
    msg1 += f"   آزادی: {fmt(azadi)} تومان\n"
    msg1 += f"   نیم: {fmt(nim)} تومان\n"
    msg1 += f"   امامی: {fmt(emami)} تومان\n\n"
    msg1 += f"₿ بیتکوین: ${fmt(btc_usd)}\n"
    msg1 += f"   = {fmt(btc_toman)} تومان\n\n"
    msg1 += f"💰 تتر (USDT): {fmt(usd_sell)} تومان\n\n"
    msg1 += f"📈 شاخص بورس: {fmt(bourse)}"

    send_telegram(msg1)
    print(f"  [SENT] Iran prices")

    # ============================================================
    #  BUILD MESSAGE 2: Fear & Greed + Global Market
    # ============================================================
    if fear_greed or global_market:
        msg2 = f"🧠 آنالیز بازار جهانی\n\n"

        # Fear & Greed
        if fear_greed:
            fg = fear_greed
            msg2 += f"{fg['emoji']} شاخص ترس و طمع: {fg['value']}/100\n"
            msg2 += f"   وضعیت: {fg['classification']}\n"
            msg2 += f"   میانگین ۷ روزه: {fg['avg_7d']}\n"
            msg2 += f"   روند: {fg['trend']}\n\n"

        # Global Market
        if global_market:
            gm = global_market
            msg2 += f"🌍 بازار جهانی:\n"
            msg2 += f"   ارزش کل بازار: ${gm['total_market_cap_t']}T\n"
            msg2 += f"   حجم معاملات ۲۴ ساعت: ${gm['total_volume_t']}T\n"
            msg2 += f"   تسلط بیتکوین: {gm['btc_dominance']}%\n"
            msg2 += f"   تغییرات ۲۴ ساعت: {gm['market_cap_change_24h']}%\n\n"

            # Trending
            if gm["trending"]:
                msg2 += f"🔥 ترند امروز:\n"
                for name, symbol, rank in gm["trending"][:3]:
                    msg2 += f"   {name} (#{rank})\n"

            # Top gainers/losers
            if gm["top_gainers"]:
                msg2 += f"\n📈 بیشترین رشد ۲۴ ساعت:\n"
                for name, symbol, change in gm["top_gainers"]:
                    msg2 += f"   {symbol}: +{change:.1f}%\n"

            if gm["top_losers"]:
                msg2 += f"\n📉 بیشترین افت ۲۴ ساعت:\n"
                for name, symbol, change in gm["top_losers"]:
                    msg2 += f"   {symbol}: {change:.1f}%\n"

        send_telegram(msg2)
        print(f"  [SENT] Global analysis")

    # ============================================================
    #  BUILD MESSAGE 3: Iran vs Global Comparison
    # ============================================================
    if global_market:
        # Iran BTC price vs global
        iran_btc_premium = ((usd_sell * btc_usd) - (btc_usd * usd_sell)) / (btc_usd * usd_sell) * 100

        # Gold comparison: ounce in Iran vs international
        # International gold ~$3,200/oz (31.1g), Iran gold per gram in toman
        # ounce_usd from bonbast is the international price
        iran_gold_per_oz = gold * 31.1  # convert gram to ounce in toman
        intl_gold_per_oz_toman = ounce_usd * usd_sell
        gold_premium = ((iran_gold_per_oz - intl_gold_per_oz_toman) / intl_gold_per_oz_toman * 100) if intl_gold_per_oz_toman > 0 else 0

        msg3 = f"📊 مقایسه ایران و جهان\n\n"
        msg3 += f"🥇 طلا:\n"
        msg3 += f"   ایران: {fmt(gold)} تومان/گرم\n"
        msg3 += f"   جهانی: {fmt(round(ounce_usd * usd_sell / 31.1))} تومان/گرم\n"
        if gold_premium > 0:
            msg3 += f"   ⚠️ طلای ایران {gold_premium:.1f}% گران‌تر\n"
        else:
            msg3 += f"   ✅ طلای ایران {abs(gold_premium):.1f}% ارزان‌تر\n"

        msg3 += f"\n₿ بیتکوین:\n"
        msg3 += f"   ایران (دلار فروش): ${fmt(usd_sell)}\n"
        msg3 += f"   جهانی: ${fmt(btc_usd)}\n"

        send_telegram(msg3)
        print(f"  [SENT] Iran vs Global")

    # ============================================================
    #  BUILD MESSAGE 4: Whale Tracker
    # ============================================================
    if whales and whales["whales"]:
        msg4 = f"🐋 ردیابی نهنگ‌ها\n\n"
        msg4 += f"📡 تراکنش‌های تأیید نشده: {whales['total_unconfirmed']:,}\n"
        msg4 += f"🐋 تراکنش‌های بزرگ (>100 BTC): {len(whales['whales'])}\n"
        msg4 += f"💰 کل حجم نهنگ‌ها: {fmt(whales['total_whale_btc'])} BTC\n\n"

        msg4 += f"🔥 بزرگ‌ترین تراکنش‌ها:\n"
        for i, w in enumerate(whales["whales"][:5], 1):
            msg4 += f"   {i}. {fmt(w['btc'])} BTC (${fmt(w['usd'])})\n"
            msg4 += f"      {w['hash']}\n"

        if whales["total_whale_btc"] > 500:
            msg4 += f"\n⚠️ هشدار: حجم بالای نهنگ‌ها ممکن است نشانه تلاطیم بازار باشد!"
        elif whales["total_whale_btc"] > 100:
            msg4 += f"\n📊 فعالیت نهنگ‌ها معمولی است."

        send_telegram(msg4)
        print(f"  [SENT] Whale tracker")

    # ============================================================
    #  LOG
    # ============================================================
    log_file = os.path.join(os.path.expanduser("~"), "dollar-price-log.txt")
    log_entry = f"[{date_str}] USD:{fmt(usd_sell)}/{fmt(usd_buy)} | Gold:{fmt(gold)} | BTC:${fmt(btc_usd)} | Bourse:{fmt(bourse)}"
    if fear_greed:
        log_entry += f" | F&G:{fear_greed['value']}"
    if global_market:
        log_entry += f" | Dom:{global_market['btc_dominance']}%"

    print(log_entry)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

    if errors:
        print(f"[{date_str}] Errors: {'; '.join(errors)}")

    print(f"[{date_str}] All done! ({len(errors)} errors)")


if __name__ == "__main__":
    main()
