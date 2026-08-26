# -*- coding: utf-8 -*-
"""
Smart Financial Bot - Iran Market Analysis (Enhanced Whale Tracker)
Features:
  1. Real-time prices from bonbast.com
  2. Fear & Greed Index
  3. Global market data (BTC dominance, trending, gainers/losers)
  4. Whale Tracker (enhanced):
     - Large unconfirmed transactions
     - Known whale wallet monitoring
     - Network health (hash rate, mempool, difficulty)
     - Transaction volume analysis
     - Smart whale alerts
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
        classification_en = current["value_classification"]
        classification_fa = {
            "Extreme Fear": "\u062a\u0631\u0633 \u0634\u062f\u06cc\u062f",
            "Fear": "\u062a\u0631\u0633",
            "Neutral": "\u062e\u0646\u062b\u06cc",
            "Greed": "\u0637\u0645\u0639",
            "Extreme Greed": "\u0637\u0645\u0639 \u0634\u062f\u06cc\u062f",
        }.get(classification_en, classification_en)

        if value <= 20:
            emoji = "\U0001f631"
        elif value <= 40:
            emoji = "\U0001f630"
        elif value <= 60:
            emoji = "\U0001f610"
        elif value <= 80:
            emoji = "\U0001f60f"
        else:
            emoji = "\U0001f911"

        values_7d = [int(d["value"]) for d in data]
        avg_7d = sum(values_7d) // len(values_7d)
        trend = "\U0001f4c8" if values_7d[0] > values_7d[-1] else "\U0001f4c9" if values_7d[0] < values_7d[-1] else "\u27a1\ufe0f"

        return {
            "value": value,
            "emoji": emoji,
            "classification": classification_fa,
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
        r = s.get("https://api.coingecko.com/api/v3/global", timeout=15)
        g = r.json()["data"]

        r2 = s.get("https://api.coingecko.com/api/v3/search/trending", timeout=15)
        trending = r2.json()["coins"][:5]

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
#  SECTION 4: Enhanced Whale Tracker
# ============================================================

# Known whale wallets (label, address)
KNOWN_WHALE_WALLETS = [
    ("Satoshi Nakamoto", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"),
    ("Binance Cold 1", "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"),
    ("Binance Cold 2", "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j"),
    ("Bitfinex Cold", "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j"),
    ("MicroStrategy", "bc1qazcm763858nkj2dzrz0h8w3ny0yg5g3ykhp6e"),
    ("Grayscale GBTC", "bc1ql49ydapnjafl5t2cp9zqpjwe6pdgmxy98859v2"),
]


def fetch_whale_unconfirmed():
    """Fetch large unconfirmed BTC transactions."""
    try:
        s = requests.Session()
        s.verify = False
        r = s.get("https://blockchain.info/unconfirmed-transactions?format=json", timeout=20)
        txs = r.json()["txs"]

        whales = []
        for t in txs:
            out_value = sum(o.get("value", 0) for o in t.get("out", [])) / 1e8
            in_value = sum(i.get("value", 0) for i in t.get("inputs", [])) / 1e8
            if out_value >= 100:
                whales.append({
                    "hash": t["hash"][:16] + "...",
                    "btc": round(out_value, 2),
                    "in_btc": round(in_value, 2),
                    "inputs": len(t.get("inputs", [])),
                    "outputs": len(t.get("out", [])),
                    "fee": round(t.get("fee", 0) / 1e8, 8),
                })

        whales.sort(key=lambda x: x["btc"], reverse=True)
        return {
            "total_unconfirmed": len(txs),
            "whales": whales[:10],
            "total_whale_btc": round(sum(w["btc"] for w in whales), 2),
            "mega_whales": len([w for w in whales if w["btc"] >= 1000]),
            "large_whales": len([w for w in whales if 500 <= w["btc"] < 1000]),
            "medium_whales": len([w for w in whales if 100 <= w["btc"] < 500]),
        }
    except Exception as e:
        print(f"  Whale unconfirmed error: {e}", file=sys.stderr)
        return None


def fetch_whale_wallets():
    """Monitor known whale wallet balances."""
    try:
        s = requests.Session()
        s.verify = False
        active_addrs = "|".join([addr for _, addr in KNOWN_WHALE_WALLETS])
        r = s.get(f"https://blockchain.info/balance?active={active_addrs}", timeout=20)
        data = r.json()

        wallets = []
        for label, addr in KNOWN_WHALE_WALLETS:
            if addr in data:
                info = data[addr]
                balance = info["final_balance"] / 1e8
                total_received = info["total_received"] / 1e8
                n_tx = info["n_tx"]
                wallets.append({
                    "label": label,
                    "address": addr[:12] + "...",
                    "balance": round(balance, 4),
                    "balance_usd": round(balance * 80000, 0),
                    "total_received": round(total_received, 4),
                    "n_tx": n_tx,
                })

        wallets.sort(key=lambda x: x["balance"], reverse=True)
        total_btc = sum(w["balance"] for w in wallets)
        return {
            "wallets": wallets[:6],
            "total_btc": round(total_btc, 4),
            "total_usd": round(total_btc * 80000, 0),
        }
    except Exception as e:
        print(f"  Whale wallets error: {e}", file=sys.stderr)
        return None


def fetch_network_health():
    """Fetch Bitcoin network health metrics."""
    result = {}

    # Hash rate
    try:
        s = requests.Session()
        s.verify = False
        headers = {"User-Agent": "Mozilla/5.0"}
        r = s.get("https://api.blockchain.info/charts/hash-rate?timespan=7days&format=json", timeout=15, headers=headers)
        data = r.json()["values"]
        latest = data[-1]
        week_ago = data[0]
        change = ((latest["y"] - week_ago["y"]) / week_ago["y"]) * 100
        result["hash_rate"] = {
            "current": round(latest["y"], 2),
            "change_7d": round(change, 1),
            "unit": "EH/s",
        }
    except Exception as e:
        print(f"  Hash rate error: {e}", file=sys.stderr)

    # Mempool size
    try:
        s = requests.Session()
        s.verify = False
        headers = {"User-Agent": "Mozilla/5.0"}
        r = s.get("https://api.blockchain.info/charts/mempool-size?timespan=7days&format=json", timeout=15, headers=headers)
        data = r.json()["values"]
        latest = data[-1]
        avg_7d = sum(d["y"] for d in data) / len(data)
        result["mempool"] = {
            "current_mb": round(latest["y"] / 1e6, 2),
            "avg_7d_mb": round(avg_7d / 1e6, 2),
        }
    except Exception as e:
        print(f"  Mempool error: {e}", file=sys.stderr)

    # Transaction volume
    try:
        s = requests.Session()
        s.verify = False
        headers = {"User-Agent": "Mozilla/5.0"}
        r = s.get("https://api.blockchain.info/charts/estimated-transaction-volume-usd?timespan=7days&format=json", timeout=15, headers=headers)
        data = r.json()["values"]
        latest = data[-1]
        avg_7d = sum(d["y"] for d in data) / len(data)
        change = ((latest["y"] - avg_7d) / avg_7d) * 100 if avg_7d > 0 else 0
        result["tx_volume"] = {
            "current_b": round(latest["y"] / 1e9, 2),
            "avg_7d_b": round(avg_7d / 1e9, 2),
            "change_pct": round(change, 1),
        }
    except Exception as e:
        print(f"  TX volume error: {e}", file=sys.stderr)

    # Miners revenue
    try:
        s = requests.Session()
        s.verify = False
        headers = {"User-Agent": "Mozilla/5.0"}
        r = s.get("https://api.blockchain.info/charts/miners-revenue?timespan=7days&format=json", timeout=15, headers=headers)
        data = r.json()["values"]
        latest = data[-1]
        result["miners_revenue"] = {
            "current_m": round(latest["y"] / 1e6, 2),
        }
    except Exception as e:
        print(f"  Miners revenue error: {e}", file=sys.stderr)

    # Output volume (total BTC moved)
    try:
        s = requests.Session()
        s.verify = False
        headers = {"User-Agent": "Mozilla/5.0"}
        r = s.get("https://api.blockchain.info/charts/output-volume?timespan=7days&format=json", timeout=15, headers=headers)
        data = r.json()["values"]
        latest = data[-1]
        avg_7d = sum(d["y"] for d in data) / len(data)
        result["output_volume"] = {
            "current": round(latest["y"], 2),
            "avg_7d": round(avg_7d, 2),
            "change_pct": round(((latest["y"] - avg_7d) / avg_7d) * 100, 1) if avg_7d > 0 else 0,
        }
    except Exception as e:
        print(f"  Output volume error: {e}", file=sys.stderr)

    # Number of transactions
    try:
        s = requests.Session()
        s.verify = False
        headers = {"User-Agent": "Mozilla/5.0"}
        r = s.get("https://api.blockchain.info/charts/n-transactions?timespan=7days&format=json", timeout=15, headers=headers)
        data = r.json()["values"]
        latest = data[-1]
        avg_7d = sum(d["y"] for d in data) / len(data)
        result["tx_count"] = {
            "current": int(latest["y"]),
            "avg_7d": int(avg_7d),
            "change_pct": round(((latest["y"] - avg_7d) / avg_7d) * 100, 1) if avg_7d > 0 else 0,
        }
    except Exception as e:
        print(f"  TX count error: {e}", file=sys.stderr)

    return result if result else None


def build_whale_message(whale_unconfirmed, whale_wallets, network_health, btc_usd):
    """Build comprehensive whale tracker message."""
    msg = "\U0001f40b \u062a\u062d\u0644\u06cc\u0644 \u0646\u0647\u0646\u06af\u200c\u0647\u0627\n"

    # === Part 1: Unconfirmed Transactions ===
    if whale_unconfirmed:
        wu = whale_unconfirmed
        msg += "\U0001f4e1 \u062a\u0631\u0627\u06a9\u0646\u0634\u200c\u0647\u0627\u06cc \u062a\u0623\u06cc\u06cc\u062f\u0646\u0634\u062f\u0647:\n"
        msg += f"   \u06a9\u0644: {wu['total_unconfirmed']:,} \u062a\u0631\u0627\u06a9\u0646\u0634\n"
        msg += f"   \U0001f40b \u0646\u0647\u0646\u06af\u200c\u0647\u0627 (>100 BTC): {len(wu['whales'])}\n"

        if wu["mega_whales"] > 0:
            msg += f"   \u26a1 \u0645\u06cc\u06af\u0627 \u0646\u0647\u0646\u06af (>1000 BTC): {wu['mega_whales']}\n"
        if wu["large_whales"] > 0:
            msg += f"   \U0001f4b0 \u0628\u0632\u0631\u06af (>500 BTC): {wu['large_whales']}\n"

        msg += f"   \U0001f4b5 \u06a9\u0644 \u062d\u062c\u0645: {fmt(wu['total_whale_btc'])} BTC (${fmt(round(wu['total_whale_btc'] * btc_usd))})\n\n"

        if wu["whales"]:
            msg += "\U0001f525 \u0628\u0632\u0631\u06af\u062a\u0631\u06cc\u0646 \u062a\u0631\u0627\u06a9\u0646\u0634\u200c\u0647\u0627:\n"
            for i, w in enumerate(wu["whales"][:5], 1):
                tier = "\u26a1" if w["btc"] >= 1000 else "\U0001f4b0" if w["btc"] >= 500 else "\U0001f4b5"
                msg += f"   {i}. {tier} {fmt(w['btc'])} BTC (${fmt(round(w['btc'] * btc_usd))})\n"
                msg += f"      \u062e\u0631\u0648\u062c: {w['outputs']} | \u06a9\u0627\u0631\u0645\u0632\u062f: {w['hash']}\n"

        msg += "\n"

    # === Part 2: Known Whale Wallets ===
    if whale_wallets:
        ww = whale_wallets
        msg += "\U0001f3e6 \u06a9\u06cc\u0641\u200c\u067e\u0648\u0644\u200c\u0647\u0627\u06cc \u0634\u0646\u0627\u062e\u062a\u0647\u200c\u0634\u062f\u0647:\n"
        msg += f"   \U0001f4b0 \u0645\u0648\u062c\u0648\u062f\u06cc \u06a9\u0644: {fmt(ww['total_btc'])} BTC\n"

        for w in ww["wallets"][:4]:
            msg += f"   {w['label']}:\n"
            msg += f"      {fmt(w['balance'])} BTC | {w['n_tx']:,} \u062a\u0631\u0627\u06a9\u0646\u0634\n"


    # === Part 3: Network Health ===
    if network_health:
        nh = network_health
        msg += "\n\U0001f310 \u0633\u0644\u0627\u0645\u062a \u0634\u0628\u06a9\u0647 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646:\n"

        if "hash_rate" in nh:
            hr = nh["hash_rate"]
            trend = "\U0001f4c8" if hr["change_7d"] > 0 else "\U0001f4c9"
            msg += f"   \u2699\ufe0f \u0646\u0631\u062e \u0647\u0634: {hr['current']} {hr['unit']} {trend} {hr['change_7d']:+.1f}%\n"

        if "mempool" in nh:
            mp = nh["mempool"]
            status = "\u26a0\ufe0f \u0628\u0633\u06cc\u0627\u0631" if mp["current_mb"] > mp["avg_7d_mb"] * 1.5 else "\u2705 \u0639\u0627\u062f\u06cc"
            msg += f"   \U0001f4e6 \u0645\u06cc\u0645\u067e\u0648\u0644: {mp['current_mb']} MB {status}\n"

        if "tx_volume" in nh:
            tv = nh["tx_volume"]
            trend = "\U0001f4c8" if tv["change_pct"] > 0 else "\U0001f4c9"
            msg += f"   \U0001f4b5 \u062d\u062c\u0645 \u0645\u0639\u0627\u0645\u0644\u0627\u062a \u06f2\u06f4 \u0633\u0627\u0639\u062a\u0647: ${tv['current_b']}B {trend} {tv['change_pct']:+.1f}%\n"

        if "miners_revenue" in nh:
            mr = nh["miners_revenue"]
            msg += f"   \u26cf\ufe0f \u062f\u0631\u0622\u0645\u062f \u0645\u0627\u06cc\u0646\u0631\u0647\u0627: ${mr['current_m']}M\n"

        if "tx_count" in nh:
            tc = nh["tx_count"]
            trend = "\U0001f4c8" if tc["change_pct"] > 0 else "\U0001f4c9"
            msg += f"   \U0001f4ca \u062a\u0639\u062f\u0627\u062f \u062a\u0631\u0627\u06a9\u0646\u0634 \u06f2\u06f4 \u0633\u0627\u0639\u062a\u0647: {tc['current']:,} {trend} {tc['change_pct']:+.1f}%\n"

        if "output_volume" in nh:
            ov = nh["output_volume"]
            trend = "\U0001f4c8" if ov["change_pct"] > 0 else "\U0001f4c9"
            msg += f"   \U0001f4b5 \u062d\u062c\u0645 \u062e\u0631\u0648\u062c\u06cc: {fmt(ov['current'])} BTC {trend} {ov['change_pct']:+.1f}%\n"

        msg += "\n"

    # === Part 4: Smart Alerts ===
    alerts = []

    if whale_unconfirmed and whale_unconfirmed["mega_whales"] > 0:
        alerts.append(f"\u26a1 {whale_unconfirmed['mega_whales']} \u0645\u06cc\u06af\u0627 \u0646\u0647\u0646\u06af \u062f\u0631 \u0631\u0627\u0647 \u0627\u0633\u062a! \u0627\u0645\u06a9\u0627\u0646 \u062a\u0644\u0627\u0637\u06cc \u0628\u0627\u0632\u0627\u0631 \u0645\u0634\u062d\u0648\u0635 \u0628\u0627\u0634\u062f.")

    if whale_unconfirmed and whale_unconfirmed["total_whale_btc"] > 1000:
        alerts.append(f"\u26a0\ufe0f \u062d\u062c\u0645 \u0628\u0632\u0631\u06af \u0646\u0647\u0646\u06af: {fmt(whale_unconfirmed['total_whale_btc'])} BTC - \u062a\u0648\u062c\u0647 \u0628\u0647 \u062a\u0644\u0627\u0637\u06cc!")

    if network_health and network_health.get("mempool", {}).get("current_mb", 0) > network_health.get("mempool", {}).get("avg_7d_mb", 0) * 2:
        alerts.append("\U0001f6a8 \u0645\u06cc\u0645\u067e\u0648\u0644 \u0634\u0627\u062f\u06cc \u0627\u0632 \u062d\u0627\u0644 \u0639\u0627\u062f\u06cc \u0627\u0633\u062a - \u0627\u0632\u062f\u0648\u0627\u0645 \u062a\u0631\u0627\u06a9\u0646\u0634 \u0628\u0631\u0642\u06cc \u0628\u0627\u0634\u062f!")

    if network_health and network_health.get("output_volume", {}).get("change_pct", 0) > 50:
        alerts.append(f"\U0001f40b \u062d\u062c\u0645 \u062e\u0631\u0648\u062c\u06cc +{network_health['output_volume']['change_pct']}% \u0627\u0632 \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646 - \u0641\u0639\u0627\u0644\u06cc\u062a \u0646\u0647\u0646\u06af \u0628\u06cc\u0634\u062a\u0631 \u0627\u0633\u062a!")

    if network_health and network_health.get("tx_volume", {}).get("change_pct", 0) > 30:
        alerts.append(f"\U0001f4c8 \u062d\u062c\u0645 \u0645\u0639\u0627\u0645\u0644\u0627\u062a +{network_health['tx_volume']['change_pct']}% \u0627\u0632 \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646 - \u0627\u0641\u0632\u0627\u06cc\u0634 \u0641\u0639\u0627\u0644\u06cc\u062a!")

    if alerts:
        msg += "\U0001f6a8 \u0647\u0634\u062f\u0627\u0631\u0647\u0627\u06cc \u0647\u0648\u0634\u0645\u0646\u062f:\n"
        for alert in alerts:
            msg += f"   {alert}\n"

    return msg


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

    bonbast = None
    fear_greed = None
    global_market = None
    whale_unconfirmed = None
    whale_wallets = None
    network_health = None

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
        whale_unconfirmed = fetch_whale_unconfirmed()
        print("  [OK] Whale unconfirmed txs")
    except Exception as e:
        errors.append(f"Whale unconfirmed: {e}")
        print(f"  [ERR] Whale unconfirmed: {e}")

    try:
        whale_wallets = fetch_whale_wallets()
        print("  [OK] Whale wallets")
    except Exception as e:
        errors.append(f"Whale wallets: {e}")
        print(f"  [ERR] Whale wallets: {e}")

    try:
        network_health = fetch_network_health()
        print("  [OK] Network health")
    except Exception as e:
        errors.append(f"Network: {e}")
        print(f"  [ERR] Network health: {e}")

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
    #  MESSAGE 1: Iran Market Prices
    # ============================================================
    msg1 = f"\U0001f4ca \u0642\u06cc\u0645\u062a \u0644\u062d\u0638\u0647\u200c\u0627\u06cc \u0628\u0627\u0632\u0627\u0631 \u0622\u0632\u0627\u062f\n"
    msg1 += f"\U0001f550 \u0628\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc: {last_modified}\n"
    msg1 += f"\n\U0001f4b5 \u062f\u0644\u0627\u0631:\n"
    msg1 += f"   \u0641\u0631\u0648\u0634: {fmt(usd_sell)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"   \u062e\u0631\u06cc\u062f: {fmt(usd_buy)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"\n\U0001f947 \u0637\u0644\u0627 (18 \u0639\u06cc\u0627\u0631): {fmt(gold)} \u062a\u0648\u0645\u0627\u0646/\u06af\u0631\u0645\n"
    msg1 += f"   \u0627\u0646\u0633: ${fmt(ounce_usd)} = {fmt(ounce_toman)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"\n\U0001fa99 \u0633\u06a9\u0647:\n"
    msg1 += f"   \u0622\u0632\u0627\u062f\u06cc: {fmt(azadi)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"   \u0646\u06cc\u0645: {fmt(nim)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"   \u0627\u0645\u0627\u0645\u06cc: {fmt(emami)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"\n\u20bf \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646: ${fmt(btc_usd)} = {fmt(btc_toman)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"\n\U0001f4b0 \u062a\u062a\u0631 (USDT): {fmt(usd_sell)} \u062a\u0648\u0645\u0627\u0646\n"
    msg1 += f"\n\U0001f4c8 \u0634\u0627\u062e\u0635 \u0628\u0648\u0631\u0633: {fmt(bourse)}"

    send_telegram(msg1)
    print(f"  [SENT] Iran prices")

    # ============================================================
    #  MESSAGE 2: Fear & Greed + Global Market
    # ============================================================
    if fear_greed or global_market:
        msg2 = "\U0001f9e0 \u0622\u0646\u0627\u0644\u06cc\u0632 \u0628\u0627\u0632\u0627\u0631 \u062c\u0647\u0627\u0646\u06cc\n"

        if fear_greed:
            fg = fear_greed
            msg2 += f"{fg['emoji']} \u0634\u0627\u062e\u0635 \u062a\u0631\u0633 \u0648 \u0637\u0645\u0639: {fg['value']}/100\n"
            msg2 += f"   \u0648\u0636\u0639\u06cc\u062a: {fg['classification']}\n"
            msg2 += f"   \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646 7 \u0631\u0648\u0632\u0647: {fg['avg_7d']}\n"
            msg2 += f"   \u0631\u0648\u0646\u062f: {fg['trend']}\n"

        if global_market:
            gm = global_market
            msg2 += "\U0001f30d \u0628\u0627\u0632\u0627\u0631 \u062c\u0647\u0627\u0646\u06cc:\n"
            msg2 += f"   \u0627\u0631\u0632\u0634 \u06a9\u0644 \u0628\u0627\u0632\u0627\u0631: {gm['total_market_cap_t']} \u062a\u0631\u06cc\u0644\u06cc\u0648\u0646 \u062f\u0644\u0627\u0631\n"
            msg2 += f"   \u062d\u062c\u0645 \u0645\u0639\u0627\u0645\u0644\u0627\u062a 24 \u0633\u0627\u0639\u062a\u0647: {gm['total_volume_t']} \u062a\u0631\u06cc\u0644\u06cc\u0648\u0646 \u062f\u0644\u0627\u0631\n"
            msg2 += f"   \u062a\u0633\u0644\u0637 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646: {gm['btc_dominance']} \u062f\u0631\u0635\u062f\n"
            if gm['market_cap_change_24h'] > 0:
                msg2 += f"   \u062a\u063a\u06cc\u06cc\u0631\u0627\u062a 24 \u0633\u0627\u0639\u062a\u0647: +{gm['market_cap_change_24h']} \u062f\u0631\u0635\u062f \U0001f4c8\n"
            else:
                msg2 += f"   \u062a\u063a\u06cc\u06cc\u0631\u0627\u062a 24 \u0633\u0627\u0639\u062a\u0647: {gm['market_cap_change_24h']} \u062f\u0631\u0635\u062f \U0001f4c9\n"

            if gm["trending"]:
                msg2 += "\U0001f525 \u062a\u0631\u0646\u062f \u0627\u0645\u0631\u0648\u0632:\n"
                for name, symbol, rank in gm["trending"][:3]:
                    msg2 += f"   {name} (#{rank})\n"

            if gm["top_gainers"]:
                msg2 += f"\U0001f4c8 \u0628\u06cc\u0634\u062a\u0631\u06cc\u0646 \u0631\u0634\u062f 24 \u0633\u0627\u0639\u062a\u0647:\n"
                for name, symbol, change in gm["top_gainers"]:
                    msg2 += f"   {symbol}: +{change:.1f}%\n"

            if gm["top_losers"]:
                msg2 += f"\U0001f4c9 \u0628\u06cc\u0634\u062a\u0631\u06cc\u0646 \u0627\u0641\u062a 24 \u0633\u0627\u0639\u062a\u0647:\n"
                for name, symbol, change in gm["top_losers"]:
                    msg2 += f"   {symbol}: {change:.1f}%\n"

        send_telegram(msg2)
        print(f"  [SENT] Global analysis")

    # ============================================================
    #  MESSAGE 3: Iran vs Global Comparison
    # ============================================================
    if global_market:
        iran_gold_per_oz = gold * 31.1
        intl_gold_per_oz_toman = ounce_usd * usd_sell
        gold_premium = ((iran_gold_per_oz - intl_gold_per_oz_toman) / intl_gold_per_oz_toman * 100) if intl_gold_per_oz_toman > 0 else 0

        msg3 = "\U0001f4ca \u0645\u0642\u0627\u06cc\u0633\u0647 \u0627\u06cc\u0631\u0627\u0646 \u0648 \u062c\u0647\u0627\u0646\n"
        msg3 += "\U0001f947 \u0637\u0644\u0627:\n"
        msg3 += f"   \u0627\u06cc\u0631\u0627\u0646: {fmt(gold)} \u062a\u0648\u0645\u0627\u0646/\u06af\u0631\u0645\n"
        msg3 += f"   \u062c\u0647\u0627\u0646\u06cc: {fmt(round(ounce_usd * usd_sell / 31.1))} \u062a\u0648\u0645\u0627\u0646/\u06af\u0631\u0645\n"
        if gold_premium > 0:
            msg3 += f"   \u26a0\ufe0f \u0637\u0644\u0627\u06cc \u0627\u06cc\u0631\u0627\u0646 {gold_premium:.1f}% \u06af\u0631\u0627\u0646\u062a\u0631\n"
        else:
            msg3 += f"   \u2705 \u0637\u0644\u0627\u06cc \u0627\u06cc\u0631\u0627\u0646 {abs(gold_premium):.1f}% \u0627\u0631\u0632\u0627\u0646\u062a\u0631\n"

        msg3 += f"\n\u20bf \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646:\n"
        msg3 += f"   \u0642\u06cc\u0645\u062a \u062f\u0644\u0627\u0631 \u0627\u06cc\u0631\u0627\u0646: {fmt(usd_sell)} \u062a\u0648\u0645\u0627\u0646\n"
        msg3 += f"   \u0642\u06cc\u0645\u062a \u062c\u0647\u0627\u0646\u06cc \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646: ${fmt(btc_usd)}\n"

        send_telegram(msg3)
        print(f"  [SENT] Iran vs Global")

    # ============================================================
    #  MESSAGE 4: Enhanced Whale Tracker
    # ============================================================
    if whale_unconfirmed or whale_wallets or network_health:
        msg4 = build_whale_message(whale_unconfirmed, whale_wallets, network_health, btc_usd)
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
    if whale_unconfirmed:
        log_entry += f" | Whales:{len(whale_unconfirmed['whales'])}"
    if whale_wallets:
        log_entry += f" | WhaleBTC:{whale_wallets['total_btc']}"

    print(log_entry)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

    if errors:
        print(f"[{date_str}] Errors: {'; '.join(errors)}")

    print(f"[{date_str}] All done! ({len(errors)} errors)")


if __name__ == "__main__":
    main()
