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
    """Build concise whale tracker message."""
    msg = "\U0001f40b \u062a\u062d\u0644\u06cc\u0644 \u0646\u0647\u0646\u06af\u200c\u0647\u0627\n"
    alerts = []

    # Quick summary
    if whale_unconfirmed:
        wu = whale_unconfirmed
        whale_count = len(wu['whales'])
        total_btc = wu['total_whale_btc']
        if whale_count > 0 or wu['mega_whales'] > 0:
            status = "\u26a1\ufe0f \u0641\u0639\u0627\u0644"
        else:
            status = "\u2705 \u0622\u0631\u0627\u0645"
        msg += f"{status} | \u062a\u0631\u0627\u06a9\u0646\u0634: {wu['total_unconfirmed']:,} | \u0646\u0647\u0646\u06af: {whale_count} | \u062d\u062c\u0645: {fmt(total_btc)} BTC\n"
        if wu["mega_whales"] > 0:
            alerts.append(f"\u26a1 {wu['mega_whales']} \u0645\u06cc\u06af\u0627 \u0646\u0647\u0646\u06af \u062f\u0631 \u0631\u0627\u0647!")

    # Top 3 biggest transactions
    if whale_unconfirmed and whale_unconfirmed.get("whales"):
        top = whale_unconfirmed["whales"][:3]
        if top:
            msg += "\n\U0001f525 \u0628\u0632\u0631\u06af\u062a\u0631\u06cc\u0646:\n"
            for i, w in enumerate(top, 1):
                usd_val = fmt(round(w['btc'] * btc_usd))
                msg += f"   {i}. {fmt(w['btc'])} BTC (${usd_val})\n"

    # Known wallets
    if whale_wallets and whale_wallets.get("wallets"):
        msg += f"\n\U0001f3e6 \u0645\u0648\u062c\u0648\u062f\u06cc: {fmt(whale_wallets['total_btc'])} BTC\n"
        for w in whale_wallets["wallets"][:3]:
            msg += f"   {w['label']}: {fmt(w['balance'])} BTC\n"

    # Network health (compact)
    if network_health:
        nh = network_health
        parts = []
        if "mempool" in nh:
            mp = nh["mempool"]
            st = "\u26a0\ufe0f" if mp["current_mb"] > mp["avg_7d_mb"] * 1.5 else "\u2705"
            parts.append(f"\U0001f4e6 {mp['current_mb']} MB {st}")
        if "tx_volume" in nh:
            tv = nh["tx_volume"]
            trend = "\u2191" if tv["change_pct"] > 0 else "\u2193"
            parts.append(f"\U0001f4b5 ${tv['current_b']}B {trend}{abs(tv['change_pct']):.1f}%")
        if "miners_revenue" in nh:
            parts.append(f"\u26cf\ufe0f ${nh['miners_revenue']['current_m']}M")
        if parts:
            msg += f"\n\U0001f310 \u0634\u0628\u06a9\u0647: {' | '.join(parts)}\n"

    # Smart alerts
    if network_health:
        if network_health.get("output_volume", {}).get("change_pct", 0) > 50:
            alerts.append(f"\U0001f40b \u062d\u062c\u0645 +{network_health['output_volume']['change_pct']}% \u0627\u0632 \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646!")
        if network_health.get("mempool", {}).get("current_mb", 0) > network_health.get("mempool", {}).get("avg_7d_mb", 0) * 2:
            alerts.append("\U0001f6a8 \u0645\u06cc\u0645\u067e\u0648\u0644 \u0634\u0627\u062f\u06cc - \u0634\u0628\u06a9\u0647 \u0634\u0644\u0648\u063a!")

    if alerts:
        msg += "\n\U0001f6a8 " + " | ".join(alerts)

    return msg


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


def fmt(n):
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def send_telegram(text):
    """Send message and return message_id for tracking."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text},
            timeout=15,
        )
        result = resp.json()
        if result.get("ok"):
            msg_id = result["result"]["message_id"]
            # Track message ID for daily cleanup
            _track_message(msg_id)
            return True
        else:
            print(f"Telegram error: {result}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return False


def _track_message(msg_id):
    """Save message ID to daily tracking file."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        track_file = os.path.join(os.path.expanduser("~"), f"tg-msgids-{today}.txt")
        with open(track_file, "a", encoding="utf-8") as f:
            f.write(f"{msg_id}\n")
    except Exception:
        pass


def cleanup_yesterday_messages():
    """Delete all messages from yesterday."""
    try:
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        track_file = os.path.join(os.path.expanduser("~"), f"tg-msgids-{yesterday}.txt")
        if not os.path.exists(track_file):
            return

        with open(track_file, "r", encoding="utf-8") as f:
            msg_ids = [int(line.strip()) for line in f if line.strip()]

        if not msg_ids:
            os.remove(track_file)
            return

        deleted = 0
        failed = 0
        for mid in msg_ids:
            try:
                resp = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage",
                    json={"chat_id": TELEGRAM_CHANNEL, "message_id": mid},
                    timeout=10,
                )
                if resp.json().get("ok"):
                    deleted += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        print(f"  Cleanup: deleted {deleted}/{len(msg_ids)} messages from {yesterday}")
        os.remove(track_file)
    except Exception as e:
        print(f"  Cleanup error: {e}", file=sys.stderr)


# ============================================================
#  MAIN
# ============================================================
def main():
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")

    # Cleanup yesterday's messages at start of each run
    cleanup_yesterday_messages()

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
    #  MESSAGE 4: Enhanced Whale Tracker
    # ============================================================
    if whale_unconfirmed or whale_wallets or network_health:
        msg4 = build_whale_message(whale_unconfirmed, whale_wallets, network_health, btc_usd)
        send_telegram(msg4)
        print(f"  [SENT] Whale tracker")

    # ============================================================
    #  MESSAGE 5: Morning Summary (only at 8 AM Iran time)
    # ============================================================
    iran_hour = (now.hour + 3) % 24  # Approximate Iran time (UTC+3:30)
    if iran_hour == 8 and now.minute < 30:
        yesterday_usd = usd_sell
        yesterday_gold = gold
        yesterday_btc = btc_usd
        # Try to read last log entry for comparison
        log_file = os.path.join(os.path.expanduser("~"), "dollar-price-log.txt")
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if lines:
                last = lines[-1]
                import re as _re
                m_usd = _re.search(r'USD:(\d[\d,]+)', last)
                m_gold = _re.search(r'Gold:(\d[\d,]+)', last)
                m_btc = _re.search(r'BTC:\$(\d[\d,.]+)', last)
                if m_usd:
                    yesterday_usd = int(m_usd.group(1).replace(',', ''))
                if m_gold:
                    yesterday_gold = int(m_gold.group(1).replace(',', ''))
                if m_btc:
                    yesterday_btc = float(m_btc.group(1).replace(',', ''))
        except Exception:
            pass

        usd_change = ((usd_sell - yesterday_usd) / yesterday_usd * 100) if yesterday_usd > 0 else 0
        gold_change = ((gold - yesterday_gold) / yesterday_gold * 100) if yesterday_gold > 0 else 0
        btc_change = ((btc_usd - yesterday_btc) / yesterday_btc * 100) if yesterday_btc > 0 else 0

        msg5 = f"\U0001f305 صبح بخیر | خلاصه صبحگاهی بازار\n\n"
        msg5 += f"\U0001f550 {last_modified}\n\n"
        msg5 += f"\U0001f4b5 دلار: {fmt(usd_sell)} تومان "
        if usd_change > 0:
            msg5 += f"\U0001f4c8 +{usd_change:.2f}%\n"
        elif usd_change < 0:
            msg5 += f"\U0001f4c9 {usd_change:.2f}%\n"
        else:
            msg5 += "\u27a1\ufe0f 0%\n"

        msg5 += f"\U0001f947 طلا: {fmt(gold)} تومان/گرم "
        if gold_change > 0:
            msg5 += f"\U0001f4c8 +{gold_change:.2f}%\n"
        elif gold_change < 0:
            msg5 += f"\U0001f4c9 {gold_change:.2f}%\n"
        else:
            msg5 += "\u27a1\ufe0f 0%\n"

        msg5 += f"\u20bf بیتکوین: ${fmt(btc_usd)} "
        if btc_change > 0:
            msg5 += f"\U0001f4c8 +{btc_change:.2f}%\n"
        elif btc_change < 0:
            msg5 += f"\U0001f4c9 {btc_change:.2f}%\n"
        else:
            msg5 += "\u27a1\ufe0f 0%\n"

        if fear_greed:
            msg5 += f"\n{fear_greed['emoji']} ترس و طمع: {fear_greed['value']}/100 ({fear_greed['classification']})\n"

        if global_market:
            msg5 += f"\U0001f30d ارزش کل بازار: {global_market['total_market_cap_t']} تریلیون دلار\n"

        send_telegram(msg5)
        print(f"  [SENT] Morning summary")

    # ============================================================
    #  MESSAGE 6: Daily Market Ranking
    # ============================================================
    # Calculate changes from log
    log_file = os.path.join(os.path.expanduser("~"), "dollar-price-log.txt")
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) >= 2:
            last = lines[-1]
            import re as _re
            m_usd = _re.search(r'USD:(\d[\d,]+)', last)
            m_gold = _re.search(r'Gold:(\d[\d,]+)', last)
            m_btc = _re.search(r'BTC:\$(\d[\d,.]+)', last)
            prev_usd = int(m_usd.group(1).replace(',', '')) if m_usd else 0
            prev_gold = int(m_gold.group(1).replace(',', '')) if m_gold else 0
            prev_btc = float(m_btc.group(1).replace(',', '')) if m_btc else 0

            ranking = []
            if prev_usd > 0:
                usd_pct = ((usd_sell - prev_usd) / prev_usd * 100)
                ranking.append(("دلار", usd_pct))
            if prev_gold > 0:
                gold_pct = ((gold - prev_gold) / prev_gold * 100)
                ranking.append(("طلا", gold_pct))
            if prev_btc > 0:
                btc_pct = ((btc_usd - prev_btc) / prev_btc * 100)
                ranking.append(("بیتکوین", btc_pct))
            if global_market and global_market.get("market_cap_change_24h"):
                ranking.append(("بازار کلی", global_market["market_cap_change_24h"]))

            if ranking:
                ranking.sort(key=lambda x: x[1], reverse=True)

                msg6 = f"\U0001f3c6 رتبه‌بندی بازارها امروز\n\n"
                medals = ["\U0001f947", "\U0001f948", "\U0001f949", "\U0001f94a"]
                for i, (name, pct) in enumerate(ranking[:4]):
                    medal = medals[i] if i < len(medals) else f"{i+1}."
                    if pct > 0:
                        msg6 += f"{medal} {name}: \U0001f4c8 +{pct:.2f}%\n"
                    elif pct < 0:
                        msg6 += f"{medal} {name}: \U0001f4c9 {pct:.2f}%\n"
                    else:
                        msg6 += f"{medal} {name}: \u27a1\ufe0f 0%\n"

                winner = ranking[0]
                loser = ranking[-1]
                if winner[1] > 0:
                    msg6 += f"\n\U0001f3c5 برنده امروز: {winner[0]} (+{winner[1]:.2f}%)\n"
                if loser[1] < 0:
                    msg6 += f"\U0001f534 بازنده امروز: {loser[0]} ({loser[1]:.2f}%)\n"

                send_telegram(msg6)
                print(f"  [SENT] Market ranking")
    except Exception as e:
        print(f"  [SKIP] Ranking: {e}", file=sys.stderr)

    # ============================================================
    #  MESSAGE 7: BTC Dominance
    # ============================================================
    if global_market:
        dom = global_market["btc_dominance"]
        if dom > 60:
            dom_status = "\U0001f4c8 بیتکوین غالب‌تر شده — آلت‌کوین‌ها ضعیف‌تر"
        elif dom < 45:
            dom_status = "\U0001f4c9 آلت‌کوین‌ها قوی‌تر شده‌اند"
        else:
            dom_status = "\u27a1\ufe0f تعادل نسبی در بازار"

        eth_dominance = round(100 - dom - 20, 1)  # Approximate
        msg7 = f"\U0001f4ca درصد تسلط بازارها\n\n"
        msg7 += f"\u20bf بیتکوین: {dom}%\n"
        msg7 += f"\U0001f7e2 آلت‌کوین‌ها: ~{round(100 - dom, 1)}%\n\n"
        msg7 += f"{dom_status}\n\n"
        msg7 += f"\U0001f4b5 ارزش کل بازار: {global_market['total_market_cap_t']} تریلیون دلار\n"
        msg7 += f"\U0001f4b0 حجم معاملات ۲۴ ساعته: {global_market['total_volume_t']} تریلیون دلار\n"

        if global_market["market_cap_change_24h"] > 0:
            msg7 += f"\n\U0001f4c8 بازار +{global_market['market_cap_change_24h']}٪ در ۲۴ ساعت — صعودی"
        else:
            msg7 += f"\n\U0001f4c9 بازار {global_market['market_cap_change_24h']}٪ در ۲۴ ساعت — نزولی"

        send_telegram(msg7)
        print(f"  [SENT] BTC dominance")

    # ============================================================
    #  MESSAGE 8: Daily Educational Tip
    # ============================================================
    tips = [
        "\U0001f4a1 آربیتراژ یعنی خرید ارزان در یکجا و فروش گران‌تر در جای دیگر. مثلاً خرید بیتکوین از صرافی ایرانی و فروش در بایننس.",
        "\U0001f4a1 حمایت (Support) سطحی است که قیمت به آن رسیده و برگشته. مقاومت (Resistance) سطحی است که قیمت نتوانسته از آن رد شود.",
        "\U0001f4a1 RSI زیر ۳۰ یعنی فروش بیش از حد ( oportunidad خرید)، بالای ۷۰ یعنی خرید بیش از حد ( oportunidad فروش).",
        "\U0001f4a1 هاوینگ بیتکوین هر ۴ سال رخ می‌دهد و پاداش ماینرها نصف می‌شود — تاریخاً قیمت پس از آن افزایش یافته.",
        "\U0001f4a1 حجم معاملات بالا + قیمت صعودی = روند قوی. حجم پایین + قیمت صعودی = احتمال برگشت.",
        "\U0001f4a1 میانگین متحرک ۲۰۰ روزه (MA200) مهم‌ترین خط حمایت/مقاومت بلندمدت بیتکوین است.",
        "\U0001f4a1 وقتی میمپول شلوغ است، کارمزد تراکنش بالا می‌رود. بهتر است در ساعات کم‌ترافیک تراکنش بزنید.",
        "\U0001f4a1 حداکثر تعداد بیتکوین ۲۱ میلیون است — کمیابی دلیل اصلی ارزش بیتکوین است.",
        "\U0001f4a1 کیف‌پول سرد (Cold Wallet) آفلاین است و هک نمی‌شود. کیف‌پول گرم (Hot Wallet) آنلاین و راحت‌تر ولی کم‌امن‌تر است.",
        "\U0001f4a1 فدرال رزرو (Fed) نرخ بهره را بالا ببرد = دلار قوی‌تر و بیتکوین ضعیف‌تر. پایین بیاورد = برعکس.",
        "\U0001f4a1 شاخص ترس و طمع زیر ۲۰ = ترس شدید = بهترین زمان خرید بلندمدت. بالای ۸۰ = طمع شدید = زمان فروش.",
        "\U0001f4a1 نهنگ (Whale) کسی است که بیش از ۱۰۰۰ بیتکوین دارد. حرکت آن‌ها می‌تواند بازار را تکان دهد.",
        "\U0001f4a1 DCA یعنی خرید منظم و کم‌مقدار (مثلاً هر هفته) — بهترین استراتژی برای سرمایه‌گذاری بلندمدت.",
        "\U0001f4a1 طلای ۱۸ عیار یعنی ۷۵٪ طلای خالص. ۲۴ عیار = ۹۹.۹٪ خالص. هرچه عیار بالاتر، گران‌تر.",
        "\U0001f4a1 انس طلا (Ounce) واحد جهانی قیمت طلاست = ۳۱.۱ گرم. قیمت طلای ایران = انس × نرخ دلار ÷ ۳۱.۱",
    ]
    # Pick tip based on day of year for consistency
    day_of_year = now.timetuple().tm_yday
    tip_index = day_of_year % len(tips)
    msg8 = f"\U0001f4d6 نکته آموزشی امروز\n\n{tips[tip_index]}"
    send_telegram(msg8)
    print(f"  [SENT] Daily tip")

    # ============================================================
    #  MESSAGE 9: Whale Alert (only if > 500 BTC found)
    # ============================================================
    if whale_unconfirmed and whale_unconfirmed["whales"]:
        big_whales = [w for w in whale_unconfirmed["whales"] if w["btc"] >= 500]
        if big_whales:
            msg9 = f"\u26a1 \u0647\u0634\u062f\u0627\u0631 \u0646\u0647\u0646\u06af!\n\n"
            msg9 += f"{len(big_whales)} \u062a\u0631\u0627\u06a9\u0646\u0634 \u0628\u0632\u0631\u06af \u062a\u0623\u06cc\u06cc\u062f \u0634\u062f:\n\n"
            for i, w in enumerate(big_whales[:5], 1):
                usd_val = round(w["btc"] * btc_usd)
                if w["btc"] >= 1000:
                    tier = "\u26a1\ufe0f \u0645\u06cc\u06af\u0627"
                else:
                    tier = "\U0001f4b0 \u0628\u0632\u0631\u06af"
                msg9 += f"{i}. {tier} {fmt(w['btc'])} BTC\n"
                msg9 += f"   = ${fmt(usd_val)}\n"
                msg9 += f"   \u06a9\u0648\u0631\u0648\u06cc: {w['hash']}\n\n"

            if len(big_whales) >= 3:
                msg9 += f"\u26a0\ufe0f {len(big_whales)} \u062a\u0631\u0627\u06a9\u0646\u0634 \u0628\u0632\u0631\u06af \u062f\u0631 \u0631\u0627\u0647 \u0627\u0633\u062a! \u0641\u0639\u0627\u0644\u06cc\u062a \u0646\u0647\u0646\u06af \u0628\u0631\u0642\u06cc \u0627\u0633\u062a."
            else:
                msg9 += f"\U0001f4b5 \u062d\u062c\u0645 \u06a9\u0644: {fmt(whale_unconfirmed['total_whale_btc'])} BTC\n"
                msg9 += f"\U0001f4ca \u0641\u0639\u0627\u0644\u06cc\u062a \u0646\u0647\u0646\u06af \u0645\u0639\u0645\u0648\u0644\u06cc \u0627\u0633\u062a."

            send_telegram(msg9)
            print(f"  [SENT] Whale alert")

    # ============================================================
    #  MESSAGE 10: Weekly Fear & Greed Analysis (every Sunday)
    # ============================================================
    if fear_greed and now.weekday() == 6:  # Sunday
        fg = fear_greed
        values_7d = fg["history"]
        max_val = max(values_7d)
        min_val = min(values_7d)
        range_val = max_val - min_val

        msg10 = f"\U0001f9e0 \u062a\u062d\u0644\u06cc\u0644 \u0647\u0641\u062a\u06af\u06cc \u062a\u0631\u0633 \u0648 \u0637\u0645\u0639\n\n"
        msg10 += f"\U0001f4c5 \u06af\u0632\u0627\u0631\u0634 \u06f7 \u0631\u0648\u0632\u0647:\n\n"

        # Visual bar
        bar_len = 20
        filled = int(fg["value"] / 100 * bar_len)
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
        msg10 += f"\u062a\u0631\u0633: [{bar}] {fg['value']}/100\n\n"

        # Daily breakdown
        days_name = ["\u0634\u0646\u0628\u0647", "\u062c\u0645\u0639\u0647", "\u062f\u0634\u0646\u0628\u0647", "\u0633\u0647\u200c\u0634\u0646\u0628\u0647", "\u0686\u0647\u0627\u0631\u0634\u0646\u0628\u0647", "\u067e\u0646\u062c\u0634\u0646\u0628\u0647", "\u0627\u0645\u0631\u0648\u0632"]
        for i, val in enumerate(values_7d):
            if val <= 25:
                emoji = "\U0001f631"
            elif val <= 50:
                emoji = "\U0001f610"
            else:
                emoji = "\U0001f60f"
            msg10 += f"   {days_name[i]}: {val} {emoji}\n"

        msg10 += f"\n\u0645\u06cc\u0627\u0646\u06af\u06cc\u0646: {fg['avg_7d']}\n"
        msg10 += f"\u0628\u06cc\u0634\u062a\u0631\u06cc\u0646: {max_val}\n"
        msg10 += f"\u06a9\u0645\u062a\u0631\u06cc\u0646: {min_val}\n"
        msg10 += f"\u0646\u0648\u0633\u0627\u0646: {range_val} واحد\n\n"

        if fg["value"] > fg["avg_7d"]:
            msg10 += f"\U0001f4c8 \u0628\u0627\u0632\u0627\u0631 \u0628\u0631\u0648\u0632 \u0637\u0645\u0639\u06cc\u062a\u0631 \u0634\u062f\u0647 \u0627\u0633\u062a.\n"
        elif fg["value"] < fg["avg_7d"]:
            msg10 += f"\U0001f4c9 \u0628\u0627\u0632\u0627\u0631 \u062a\u0631\u0633\u06cc \u0628\u06cc\u0634\u062a\u0631 \u0634\u062f\u0647 \u0627\u0633\u062a.\n"
        else:
            msg10 += f"\u27a1\ufe0f \u0628\u0627\u0632\u0627\u0631 \u062a\u063a\u06cc\u06cc\u0631 \u0646\u06a9\u0631\u062f\u0647 \u0627\u0633\u062a.\n"

        if fg["value"] <= 25:
            msg10 += f"\n\U0001f4a1 \u062a\u0631\u0633 \u0634\u062f\u06ccد = \u0645\u0648\u0642\u0639 \u062e\u0631\u06cc\u062f \u0628\u0631\u0627ی \u0627\u0646د\u0627\u0632\u0647 \u0628\u0644ند\u0645د."
        elif fg["value"] >= 75:
            msg10 += f"\n\U0001f4a1 \u0637\u0645\u0639 \u0634\u062f\u06cc\u062f = \u0645\u0648\u0642\u0639 \u0641\u0631\u0648\u0634 \u0628\u0631\u0627\u06cc \u0627\u0646دا\u0632\u0647 \u0628\u0644ند\u0645د."

        send_telegram(msg10)
        print(f"  [SENT] Weekly F&G analysis")

    # ============================================================
    #  MESSAGE 11: Enhanced Iran vs Global Comparison
    # ============================================================
    # This is an improved version of msg3 with more details
    if global_market:
        iran_gold_per_oz = gold * 31.1
        intl_gold_per_oz_toman = ounce_usd * usd_sell
        gold_premium = ((iran_gold_per_oz - intl_gold_per_oz_toman) / intl_gold_per_oz_toman * 100) if intl_gold_per_oz_toman > 0 else 0

        # BTC comparison
        btc_iran_toman = usd_sell * btc_usd
        btc_premium = 0  # Usually same price

        # Tether = dollar in practice
        tether_premium = ((usd_sell - usd_buy) / usd_buy * 100) if usd_buy > 0 else 0

        msg11 = f"\U0001f4ca \u0645\u0642\u0627\u06cc\u0633\u0647 \u0627\u06cc\u0631\u0627\u0646 \u0648 \u062c\u0647\u0627\u0646\n\n"

        # Gold comparison
        intl_gold_per_gram = round(ounce_usd * usd_sell / 31.1)
        msg11 += f"\U0001f947 \u0637\u0644\u0627:\n"
        msg11 += f"   \u0627\u06cc\u0631\u0627\u0646: {fmt(gold)} \u062a\u0648\u0645\u0627\u0646/\u06af\u0631\u0645\n"
        msg11 += f"   \u062c\u0647\u0627\u0646\u06cc: {fmt(intl_gold_per_gram)} \u062a\u0648\u0645\u0627\u0646/\u06af\u0631\u0645\n"
        if gold_premium > 10:
            msg11 += f"   \u26a0\ufe0f \u0637\u0644\u0627\u06cc \u0627\u06cc\u0631\u0627\u0646 {gold_premium:.1f}% \u06af\u0631\u0627\u0646\u062a\u0631 \u0627\u0632 \u062c\u0647\u0627\u0646\u06cc\n"
            msg11 += f"   \U0001f4a1 \u0627\u0645کان \u0622ربیتراژ \u0628\u0627شد\n"
        elif gold_premium < -5:
            msg11 += f"   \U0001f4a1 \u0637\u0644\u0627\u06cc \u0627\u06cc\u0631\u0627\u0646 {abs(gold_premium):.1f}% \u0627\u0631\u0632\u0627\u0646\u062a\u0631 \u0627\u0632 \u062c\u0647\u0627\u0646\u06cc\n"
        else:
            msg11 += f"   \u2705 \u0642\u06cc\u0645\u062a \u0645\u0639\u062a\u062f\u0644 \u0627\u0633\u062a\n"

        # BTC comparison
        msg11 += f"\n\u20bf \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646:\n"
        msg11 += f"   \u0642\u06cc\u0645\u062a \u062c\u0647\u0627\u0646\u06cc: ${fmt(btc_usd)}\n"
        msg11 += f"   \u0642\u06cc\u0645\u062a \u0628\u0627 \u062f\u0644\u0627\u0631 \u0627\u06cc\u0631\u0627\u0646: {fmt(btc_iran_toman)} \u062a\u0648\u0645\u0627\u0646\n"

        # ETH price
        try:
            s = requests.Session()
            s.verify = False
            r = s.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=10)
            eth_data = r.json()
            eth_usd = eth_data["ethereum"]["usd"]
            eth_toman = round(eth_usd * usd_sell)
            msg11 += f"\n\u26a1 \u0627تر\u06cc\u0648\u0645:\n"
            msg11 += f"   \u0642\u06cc\u0645\u062a \u062c\u0647\u0627\u0646\u06cc: ${fmt(eth_usd)}\n"
            msg11 += f"   \u0642\u06cc\u0645\u062a \u0628\u0627 \u062f\u0644\u0627\u0631 \u0627\u06cc\u0631\u0627\u0646: {fmt(eth_toman)} \u062a\u0648\u0645\u0627\u0646\n"
        except Exception:
            pass

        # Tether note
        msg11 += f"\n\U0001f4b0 \u062a\u062a\u0631 (USDT) = \u062f\u0644\u0627\u0631 \u062fیج\u06ccت\u0627\u0644\u06cc = {fmt(usd_sell)} \u062a\u0648\u0645\u0627\u0646\n"

        send_telegram(msg11)
        print(f"  [SENT] Enhanced Iran vs Global")

    # ============================================================
    #  MESSAGE 12: Economic Calendar (every 4 hours)
    # ============================================================
    if now.hour % 4 == 0:  # Every 4 hours
        try:
            s = requests.Session()
            s.verify = False
            s.headers.update({"User-Agent": "Mozilla/5.0"})
            r = s.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=15)
            all_events = r.json()

            # Filter USD events and high/medium impact
            usd_events = []
            for ev in all_events:
                if ev.get("country") not in ("USD", "All"):
                    continue
                impact = ev.get("impact", "Low")
                title = ev.get("title", "")
                date_str_ev = ev.get("date", "")
                if not date_str_ev:
                    continue

                # Parse the ISO date and convert to Tehran time (UTC+3:30)
                try:
                    from datetime import datetime as _dt, timedelta, timezone
                    # Parse ISO format with timezone info preserved
                    # Example: 2026-08-26T08:30:00-04:00 (EDT)
                    dt_with_tz = _dt.fromisoformat(date_str_ev)
                    if dt_with_tz.tzinfo is not None:
                        # Convert to UTC first, then to Tehran (UTC+3:30)
                        dt_utc = dt_with_tz.astimezone(timezone.utc)
                        dt_teheran = dt_utc + timedelta(hours=3, minutes=30)
                    else:
                        # No timezone info: assume UTC and add 3:30
                        dt_teheran = dt_with_tz + timedelta(hours=3, minutes=30)
                    date_formatted = dt_teheran.strftime("%Y/%m/%d %H:%M")
                    weekday_fa = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
                    day_name = weekday_fa[dt_teheran.weekday()]
                except Exception:
                    date_formatted = date_str_ev
                    day_name = ""

                # Impact emoji
                if impact == "High":
                    impact_emoji = "🔴"
                elif impact == "Medium":
                    impact_emoji = "🟡"
                else:
                    impact_emoji = "🟢"

                usd_events.append((impact_emoji, title, date_formatted, day_name, impact))

            # Sort by date
            usd_events.sort(key=lambda x: x[2])

            # Filter only high impact (🔴)
            high_events = [e for e in usd_events if e[4] == "High"]

            if high_events:
                msg12 = f"\U0001f4c5 \u062a\u0642\u0648\u06cc\u0645 \u0627\u0642\u062a\u0635\u0627\u062f\u06cc \u062f\u0644\u0627\u0631\n\n"
                msg12 += f"\u0628\u0627\u0628\u0631\u062a\u0631\u06cc\u0646 \u062a\u0623\u062b\u0631 \u0627\u0633\u062a:\n\n"

                for emoji, title, date_f, day_n, impact in high_events:
                    # Short format: day + time only
                    # date_f is like "2026/08/29 12:30"
                    parts = date_f.split(" ")
                    time_part = parts[1] if len(parts) > 1 else date_f
                    if day_n:
                        msg12 += f"{emoji} {title}\n"
                        msg12 += f"   \U0001f552 {day_n} {time_part}\n\n"
                    else:
                        msg12 += f"{emoji} {title}\n"
                        msg12 += f"   \U0001f552 {date_f}\n\n"

                send_telegram(msg12)
                print(f"  [SENT] Economic calendar")
            else:
                print(f"  [SKIP] No high impact USD events")
        except Exception as e:
            print(f"  [ERR] Calendar: {e}", file=sys.stderr)

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
