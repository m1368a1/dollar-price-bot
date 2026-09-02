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

from concurrent.futures import ThreadPoolExecutor, as_completed

from datetime import datetime



warnings.filterwarnings("ignore", message="Unverified HTTPS request")



# === CONFIG ===

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@robomohsen")





# Module-level variable for top coins data (used by dashboard)
_TOP10_COINS = []

# ===============================================================

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

#  SECTION 2: Iran Stock Market (TSETMC)

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


def fetch_crypto_rsi_report():
    """Fetch grouped hourly and daily RSI using Binance.US, with CoinGecko fallback."""
    coins = [("BTCUSDT", "بیتکوین"), ("ETHUSDT", "اتریوم"), ("BNBUSDT", "BNB"), ("SOLUSDT", "سولانا"), ("XRPUSDT", "ریپل"), ("ADAUSDT", "کاردانو"), ("DOGEUSDT", "دوج‌کوین"), ("AVAXUSDT", "آوالانچ"), ("LINKUSDT", "چین‌لینک"), ("DOTUSDT", "پولکادات")]
    coin_ids = {"BTCUSDT":"bitcoin", "ETHUSDT":"ethereum", "BNBUSDT":"binancecoin", "SOLUSDT":"solana", "XRPUSDT":"ripple", "ADAUSDT":"cardano", "DOGEUSDT":"dogecoin", "AVAXUSDT":"avalanche-2", "LINKUSDT":"chainlink", "DOTUSDT":"polkadot"}
    report = {"low_hourly": [], "high_hourly": [], "low_daily": [], "high_daily": []}
    def calculate(closes, period=14):
        if len(closes) <= period:
            return None
        gains, losses = [], []
        for previous, current in zip(closes[-period-1:-1], closes[-period:]):
            delta = current - previous
            gains.append(max(delta, 0)); losses.append(max(-delta, 0))
        gain = sum(gains) / period; loss = sum(losses) / period
        return 100.0 if loss == 0 else 100 - (100 / (1 + gain / loss))
    def add(timeframe, name, value):
        if value < 40: report[f"low_{timeframe}"].append((name, round(value, 1)))
        elif value > 60: report[f"high_{timeframe}"].append((name, round(value, 1)))
    session = requests.Session(); session.headers.update({"User-Agent": "Mozilla/5.0"})
    for symbol, name in coins:
        for interval, key in (("1h", "hourly"), ("1d", "daily")):
            closes = None
            try:
                r = session.get("https://api.binance.us/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": 100}, timeout=12)
                r.raise_for_status(); closes = [float(row[4]) for row in r.json()]
            except Exception:
                try:
                    coin_id = coin_ids[symbol]
                    days = "2" if key == "hourly" else "90"
                    r = session.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart", params={"vs_currency":"usd", "days":days}, timeout=12)
                    if r.status_code == 429:
                        raise RuntimeError("rate limited")
                    r.raise_for_status(); closes = [float(row[1]) for row in r.json().get("prices", [])]
                except Exception as exc:
                    print(f"  RSI {symbol} {key} unavailable: {exc}", file=sys.stderr)
            value = calculate(closes or [])
            if value is not None: add(key, name, value)
    return report
def build_crypto_rsi_message(report):
    """Build a concise Persian grouped RSI report."""
    if not report:
        return None
    def group(title, entries):
        if not entries:
            return f"{title}: موردی پیدا نشد\n"
        return title + ":\n" + "\n".join(f"   • {name}: {value}/100" for name, value in entries) + "\n"
    return (
        "📉📈 وضعیت RSI رمزارزها\n\n"
        "RSI کمتر از ۴۰ = ناحیه ضعف\n"
        "RSI بیشتر از ۶۰ = ناحیه قدرت\n\n"
        "⏱ ساعتی\n" +
        group("🔻 ضعیف (کمتر از ۴۰)", report["low_hourly"]) +
        group("🔺 قوی (بیشتر از ۶۰)", report["high_hourly"]) +
        "\n📅 روزانه\n" +
        group("🔻 ضعیف (کمتر از ۴۰)", report["low_daily"]) +
        group("🔺 قوی (بیشتر از ۶۰)", report["high_daily"]) +
        "\n⚠️ RSI به‌تنهایی توصیه خرید یا فروش نیست."
    )


def fetch_global_market():
    global _TOP10_COINS

    """Fetch global crypto market data from CoinGecko."""

    try:

        s = requests.Session()

        s.verify = False

        r = s.get("https://api.coingecko.com/api/v3/global", timeout=15)

        payload = r.json()
        g = payload.get("data", {})
        if not g:
            raise RuntimeError("CoinGecko global data unavailable")



        r2 = s.get("https://api.coingecko.com/api/v3/search/trending", timeout=15)

        trending_data = r2.json()
        trending = trending_data.get("coins", [])[:5] if isinstance(trending_data, dict) else []



        r3 = s.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false&price_change_percentage=24h", timeout=15)

        top_data = r3.json()
        top_coins = top_data if isinstance(top_data, list) else []

        _TOP10_COINS = top_coins

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




# Publicly labelled exchange addresses. A match is only a heuristic, not proof of a sale.
KNOWN_EXCHANGE_ADDRESSES = {
    address: label for label, address in KNOWN_WHALE_WALLETS
    if label.lower().startswith("binance") or "bitfinex" in label.lower()
}


def _tx_addresses(tx, side):
    if side == "in":
        return {item.get("prev_out", {}).get("addr") for item in tx.get("inputs", [])}
    return {item.get("addr") for item in tx.get("out", [])}


def _whale_activity_score(data):
    if not data:
        return 0
    volume_score = min(50, data.get("total_whale_btc", 0) / 100)
    count_score = min(30, len(data.get("whales", [])) * 5)
    mega_score = min(20, data.get("mega_whales", 0) * 10)
    return int(round(min(100, volume_score + count_score + mega_score)))



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
                    "exchange_in": sorted(_tx_addresses(t, "in") & set(KNOWN_EXCHANGE_ADDRESSES)),
                    "exchange_out": sorted(_tx_addresses(t, "out") & set(KNOWN_EXCHANGE_ADDRESSES)),
                    "addresses": sorted((_tx_addresses(t, "in") | _tx_addresses(t, "out")) - {None}),
                    "tier": "بسیار بزرگ" if out_value >= 1000 else "بزرگ" if out_value >= 500 else "متوسط",

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





def fmt(n):

    if isinstance(n, float):

        return f"{n:,.2f}"

    return f"{n:,}"





def send_telegram(text, chat_id=None, web_app_url=None):

    """Send one Telegram message and return success."""
    if not text:
        return False
    try:

        payload = {"chat_id": chat_id or TELEGRAM_CHANNEL, "text": text}
        if web_app_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": "\U0001f310 \u0628\u0627\u0632\u062f\u06cc\u062f\u0646 \u062f\u0634\u0628\u0648\u0631\u062f", "url": web_app_url}]]
            }
        resp = requests.post(

            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",

            json=payload,

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



def set_bot_menu_button():
    """Set the bot menu button to open the web app dashboard."""
    try:
        dashboard_url = "https://m1368a1.github.io/dollar-price-bot/dashboard.html"
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setChatMenuButton",
            json={
                "menu_button": {
                    "type": "web_app",
                    "text": "Start",
                    "web_app": {"url": dashboard_url}
                }
            },
            timeout=10,
        )
    except Exception:
        pass



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

#  Whale Message Builder (concise)

# ============================================================

def _whale_state_file():
    return os.environ.get("WHALE_STATE_FILE", os.path.join(os.path.expanduser("~"), "whale-history.json"))


def _load_whale_state():
    try:
        with open(_whale_state_file(), "r", encoding="utf-8") as handle:
            state = json.load(handle)
            return state if isinstance(state, dict) else {"addresses": {}, "events": []}
    except (FileNotFoundError, ValueError, TypeError, OSError):
        return {"addresses": {}, "events": []}


def _save_whale_state(state):
    try:
        path = _whale_state_file()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False)
    except OSError as exc:
        print(f"  Whale history save skipped: {exc}", file=sys.stderr)


def _update_whale_alerts(whales):
    """Classify repeated exchange flows and returning addresses using local history."""
    now = int(time.time())
    state = _load_whale_state()
    addresses = state.setdefault("addresses", {})
    events = state.setdefault("events", [])
    sleeping = 0
    for whale in whales:
        whale_addresses = [a for a in whale.get("addresses", []) if a]
        whale["sleeping"] = any(
            address in addresses and now - int(addresses[address]) >= 7 * 86400
            for address in whale_addresses
        )
        sleeping += int(whale["sleeping"])
        for address in whale_addresses:
            addresses[address] = now
        if whale.get("exchange_in") or whale.get("exchange_out"):
            events.append({
                "time": now,
                "exchange_in": bool(whale.get("exchange_in")),
                "exchange_out": bool(whale.get("exchange_out")),
                "btc": whale.get("btc", 0),
            })
    cutoff = now - 24 * 3600
    state["events"] = [event for event in events if int(event.get("time", 0)) >= cutoff][-200:]
    recent = state["events"]
    to_exchange = sum(1 for event in recent if event.get("exchange_out"))
    from_exchange = sum(1 for event in recent if event.get("exchange_in"))
    total_to = sum(float(event.get("btc", 0)) for event in recent if event.get("exchange_out"))
    total_from = sum(float(event.get("btc", 0)) for event in recent if event.get("exchange_in"))
    _save_whale_state(state)
    return {
        "sleeping": sleeping,
        "accumulation": from_exchange >= 2 and total_from > total_to,
        "heavy_selling": to_exchange >= 2 and total_to > total_from,
        "from_exchange_count": from_exchange,
        "to_exchange_count": to_exchange,
    }


def build_whale_message(whale_unconfirmed, whale_wallets, btc_usd):

    """Build a concise, evidence-based whale report."""
    if not whale_unconfirmed and not whale_wallets:
        return "⚠️ اطلاعات نهنگ‌ها در دسترس نیست."

    msg = "🐋 تحلیل نهنگ‌ها\n\n"
    if whale_unconfirmed:
        whales = whale_unconfirmed.get("whales", [])
        count = len(whales)
        total_btc = whale_unconfirmed.get("total_whale_btc", 0)
        score = _whale_activity_score(whale_unconfirmed)
        level = "زیاد" if score >= 65 else "متوسط" if score >= 30 else "کم"
        msg += f"📊 فعالیت فعلی: {level} ({score}/۱۰۰) | {count} تراکنش بزرگ | {fmt(total_btc)} بیتکوین\n"
        msg += f"   بسیار بزرگ: {whale_unconfirmed.get('mega_whales', 0)} | بزرگ: {whale_unconfirmed.get('large_whales', 0)} | متوسط: {whale_unconfirmed.get('medium_whales', 0)}\n"

        alerts = _update_whale_alerts(whales)
        if alerts["sleeping"]:
            msg += f"😴 نهنگ‌های بازگشته پس از خواب طولانی: {alerts['sleeping']} مورد\n"
        if alerts["accumulation"]:
            msg += "🟢 هشدار انباشت احتمالی: خروج چند انتقال بزرگ از صرافی در ۲۴ ساعت اخیر\n"
        elif alerts["heavy_selling"]:
            msg += "🔴 هشدار فروش سنگین احتمالی: ورود چند انتقال بزرگ به صرافی در ۲۴ ساعت اخیر\n"
        else:
            msg += "ℹ️ هشدار انباشت یا فروش سنگین در ۲۴ ساعت اخیر تأیید نشد.\n"

        exchange_to = sum(1 for w in whales if w.get("exchange_out"))
        exchange_from = sum(1 for w in whales if w.get("exchange_in"))
        if exchange_to or exchange_from:
            msg += f"🏦 ورود احتمالی به صرافی: {exchange_to} | خروج احتمالی از صرافی: {exchange_from}\n"
            msg += "   ⚠️ این دسته‌بندی احتمالی است و به‌تنهایی نشانه قطعی خرید یا فروش نیست.\n"
        else:
            msg += "🏦 انتقال به/از صرافی در داده‌های فعلی شناسایی نشد.\n"

        if whales:
            msg += "\n🔥 بزرگ‌ترین تراکنش‌ها:\n"
            for i, w in enumerate(whales[:3], 1):
                usd_val = round(w["btc"] * btc_usd)
                direction = "ورود احتمالی به صرافی" if w.get("exchange_out") else "خروج احتمالی از صرافی" if w.get("exchange_in") else "انتقال نامشخص"
                msg += f"{i}. {fmt(w['btc'])} بیتکوین (${fmt(usd_val)}) | {w.get('tier', 'بزرگ')} | {direction}\n"
                msg += f"   ورودی: {w.get('inputs', 0)} | خروجی: {w.get('outputs', 0)} | کارمزد: {fmt(w.get('fee', 0))} بیتکوین\n"

    if whale_wallets and whale_wallets.get("wallets"):
        msg += f"\n🏦 کیف‌پول‌های رصدشده: {fmt(whale_wallets.get('total_btc', 0))} بیتکوین\n"
        for wallet in whale_wallets["wallets"][:4]:
            msg += f"   {wallet['label']}: {fmt(wallet['balance'])} بیتکوین\n"

    msg += "\n💡 خرید یا فروش قطعی از روی یک تراکنش مشخص نمی‌شود؛ روند چند گزارش را با هم بررسی کنید."
    return msg



# ============================================================

#  SECTION: Breaking News from Investing.com RSS

# ============================================================

def fetch_investing_news():

    """Fetch breaking news headlines from Investing.com RSS feed."""

    try:

        s = requests.Session()

        s.verify = False

        s.headers.update({"User-Agent": "Mozilla/5.0"})

        r = s.get("https://www.investing.com/rss/news.rss", timeout=15)

        import xml.etree.ElementTree as ET

        root = ET.fromstring(r.text)

        items = root.findall(".//item")

        news = []

        keywords = ["usd", "dollar", "gold", "bitcoin", "btc", "oil", "fed", "inflation",

                     "interest rate", "gdp", "employment", "cpi", "treasury", "bond",

                     "crypto", "ethereum", "forex", "market", "recession", "trade war",

                     "iran", "sanctions", "oil price", "crude", "gold price"]

        for item in items[:20]:

            title = item.findtext("title", "")

            pub_date = item.findtext("pubDate", "")

            # Filter: only USD/gold/BTC/market related news

            title_lower = title.lower()

            if any(kw in title_lower for kw in keywords):

                news.append({"title": title, "date": pub_date[:16]})

        return news[:5]  # Top 5 relevant headlines

    except Exception as e:

        print(f"  Investing.com RSS error: {e}", file=sys.stderr)

        return []





def _get_seen_headlines_file():

    today = datetime.now().strftime("%Y-%m-%d")

    return os.path.join(os.path.expanduser("~"), f"news-seen-{today}.txt")





def _load_seen_headlines():

    """Load previously seen headline titles."""

    f = _get_seen_headlines_file()

    if os.path.exists(f):

        with open(f, "r", encoding="utf-8") as fh:

            return set(line.strip() for line in fh if line.strip())

    return set()





def _save_seen_headline(title):

    """Append a headline to the seen file."""

    try:

        with open(_get_seen_headlines_file(), "a", encoding="utf-8") as fh:

            fh.write(title.strip() + "\n")

    except Exception:

        pass





def _translate_news_title(title):
    """Translate financial headlines to Persian using MyMemory API with dictionary fallback."""
    import urllib.parse

    # Try MyMemory API first (free, reliable)
    try:
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0"})
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(title.strip())}&langpair=en|fa"
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and len(translated) > 5 and translated != title.strip():
                return translated
    except Exception:
        pass

    # Fallback: dictionary-based translation
    normalized = title.strip()
    phrases = [
        ("U.S. Treasury", "خزانه‌داری آمریکا"), ("US Treasury", "خزانه‌داری آمریکا"),
        ("Banque Misr", "بانک مصر"), ("foreign trade", "تجارت خارجی"),
        ("six-month war", "جنگ شش‌ماهه"), ("six month war", "جنگ شش‌ماهه"),
        ("digital gold", "طلای دیجیتال"), ("hourly levels", "سطوح ساعتی"),
        ("global markets", "بازارهای جهانی"), ("global market", "بازار جهانی"),
        ("record high", "رکورد تاریخی"), ("record low", "کف تاریخی"),
        ("all-time high", "بالاترین رکورد تاریخی"), ("safe haven", "پناهگاه امن"),
        ("interest rate", "نرخ بهره"), ("rate cuts", "کاهش نرخ بهره"),
        ("Federal Reserve", "فدرال رزرو"), ("central bank", "بانک مرکزی"),
        ("monetary policy", "سیاست پولی"), ("stock market", "بازار بورس"),
        ("oil prices", "قیمت نفت"), ("gold price", "قیمت طلا"),
        ("trade war", "جنگ تجاری"), ("sell-off", "فروش گسترده"),
        ("Strait Hormuz", "تنگه هرمز"), ("seventh month", "ماه هفتم"),
    ]
    words = [
        ("Bitcoin", "بیتکوین"), ("Ethereum", "اتریوم"), ("Goldman", "گلدمن"),
        ("Bessent", "بسنت"), ("Dollar", "دلار"), ("dollar", "دلار"),
        ("Gold", "طلا"), ("gold", "طلا"), ("Oil", "نفت"), ("oil", "نفت"),
        ("inflation", "تورم"), ("volatility", "نوسان"), ("markets", "بازارها"),
        ("market", "بازار"), ("warns", "هشدار می‌دهد"), ("says", "می‌گوید"),
        ("hits", "رکورد زد"), ("soars", "به‌شدت صعود کرد"),
        ("plunges", "سقوط کرد"), ("rallies", "صعود کرد"),
        ("amid", "در میان"), ("concerns", "نگرانی‌ها"),
        ("investors", "سرمایه‌گذاران"), ("analysts", "تحلیلگران"),
        ("officials", "مقامات"), ("supply", "عرضه"), ("recession", "رکود"),
        ("growth", "رشد"), ("debt", "بدهی"), ("yield", "بازدهی"),
        ("UAE", "امارات"), ("Egypt", "مصر"), ("America", "آمریکا"),
        ("U.S.", "آمریکا"), ("US", "آمریکا"), ("Iran", "ایران"),
        ("after", "پس از"), ("under", "در پی"), ("between", "بین"),
        ("ahead", "پیش رو"), ("key", "کلیدی"), ("insists", "اصرار دارد"),
        ("remains", "باقی مانده"), ("closed", "بسته شده"),
        ("enters", "وارد شده"), ("month", "ماه"), ("live", "زندگی"),
        ("levels", "سطوح"), ("research", "تحقیقات"), ("draws", "می‌کشد"),
        ("lessons", "درس"), ("expectations", "انتظارات"),
        ("risks", "خطرات"), ("spillover", "سرایت"), ("moves", "حرکات"),
        ("block", "مسدودکردن"), ("clearing", "تسویه"),
        ("consolidates", "تثبیت شد"), ("plunge", "سقوط"),
        ("drops", "کاهش می‌یابد"), ("falls", "افت می‌کند"),
        ("surges", "جهش می‌کند"), ("strengthens", "تقویت می‌شود"),
        ("weakens", "تضعیف می‌شود"),
    ]
    for source, target in sorted(phrases, key=lambda item: len(item[0]), reverse=True):
        normalized = normalized.replace(source, target)
    for source, target in sorted(words, key=lambda item: len(item[0]), reverse=True):
        normalized = re.sub(r'(?<![A-Za-z])' + re.escape(source) + r'(?![A-Za-z])', target, normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip(' -:;,.')
    return normalized

def build_news_message(news_list):

    """Build a message for breaking news headlines with Persian style."""

    seen = _load_seen_headlines()

    new_news = [n for n in news_list if n["title"].strip() not in seen]

    if not new_news:

        return None

    msg = chr(0x1f4e2) + " \u062e\u0628\u0631\u0647\u0627\u06cc \u0641\u0648\u0631\u06cc \u0627\u0645\u0631\u0648\u0632\n\n"
    for i, n in enumerate(new_news[:8], 1):

        translated = _translate_news_title(n["title"])

        source = n.get("source", "Investing")

        msg += f"{i}. {translated}\n"

        msg += f"   {chr(0x1f552)} {n['date']} | {source}\n\n"

        _save_seen_headline(n["title"])



    msg += f"\U0001f4a1 \u0627\u0632 Investing.com"

    return msg





# ============================================================

#  SECTION: Upcoming Economic Events Alert (Forex Factory)

# ============================================================

def fetch_upcoming_events():

    """Fetch economic events happening in the next 1-2 hours."""

    try:

        from datetime import timedelta, timezone

        s = requests.Session()

        s.verify = False

        r = s.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=15)

        all_events = r.json()



        now_utc = datetime.now(timezone.utc)

        upcoming = []

        for ev in all_events:

            if ev.get("impact") != "High":

                continue

            if ev.get("country") not in ("USD", "EUR"):

                continue

            date_str = ev.get("date", "")

            if not date_str:

                continue

            try:

                # Parse ISO date

                ev_time = datetime.fromisoformat(date_str)

                if ev_time.tzinfo is None:

                    ev_time = ev_time.replace(tzinfo=timezone.utc)

                diff = (ev_time - now_utc).total_seconds() / 3600

                # Events in the next 2 hours or just happened (< 30 min ago)

                if -0.5 <= diff <= 2:

                    # Convert to Tehran time

                    tehran_tz = timezone(timedelta(hours=3, minutes=30))

                    tehran_time = ev_time.astimezone(tehran_tz)

                    upcoming.append({

                        "title": ev.get("title", ""),

                        "country": ev.get("country", ""),

                        "impact": ev.get("impact", ""),

                        "forecast": ev.get("forecast", ""),

                        "previous": ev.get("previous", ""),

                        "tehran_time": tehran_time.strftime("%H:%M"),

                        "minutes_away": round(diff * 60),

                    })

            except Exception:

                pass

        return upcoming

    except Exception as e:

        print(f"  Forex Factory upcoming error: {e}", file=sys.stderr)

        return []





def _translate_event_title(title):

    """Translate common Forex Factory event names to Persian."""

    t = {

        "Non-Farm Employment Change": "\u062a\u063a\u06cc\u06cc\u0631 \u0627\u0634\u062a\u063a\u0627\u0644 \u062e\u0627\u0631\u062c \u0627\u0632 \u0628\u062e\u0631",

        "Core PCE Price Index m/m": "\u0634\u0627\u062e\u0635 \u0642\u06cc\u0645\u062a \u0627\u0635\u0644\u06cc PCE",

        "Advance GDP q/q": "\u062a\u0648\u0644\u06cc\u062f \u062f\u0648\u0631 \u0627\u0635\u0644\u06cc \u0627\u0645\u0631\u06cc\u06a9\u0627",

        "Prelim GDP q/q": "\u062a\u0648\u0644\u06cc\u062f \u0627\u0648\u0644\u06cc\u0647 \u062f\u0648\u0631 \u0627\u0645\u0631\u06cc\u06a9\u0627",

        "Fed Chairman": "\u0631\u0626\u06cc\u0633 \u0641\u062f\u0631\u0627\u0644 \u0631\u0632\u0631\u0648",

        "FOMC Statement": "\u0628\u06cc\u0627\u0646\u06cc\u0647 \u0641\u062f\u0631\u0627\u0644 \u0631\u0632\u0631\u0648",

        "Federal Funds Rate": "\u0646\u0631\u062e \u0628\u0647\u0631\u0647 \u0641\u062f\u0631\u0627\u0644",

        "Unemployment Rate": "\u0646\u0631\u062e \u0628\u06cc\u06a9\u0627\u0631\u06cc",

        "CPI m/m": "\u0634\u0627\u062e\u0635 \u062a\u0648\u0631\u0645",

        "Core CPI m/m": "\u0634\u0627\u062e\u0635 \u0627\u0635\u0644\u06cc \u062a\u0648\u0631\u0645",

        "Retail Sales m/m": "\u0641\u0631\u0648\u0634 \u062e\u0631\u062f\u0627\u062f \u062e\u0648\u0631\u062f\u0627\u0631\u06cc",

        "ISM Manufacturing PMI": "\u0634\u0627\u062e\u0635 \u062a\u0648\u0644\u06cc\u062f PMI",

        "JOLTS Job Openings": "\u062a\u0639\u062f\u0627\u062f \u0634\u063a\u0644\u0647\u0627\u06cc \u0634\u0628\u06a9\u0647",

    }

    for eng, fa in t.items():

        if eng in title:

            return fa

    return title





def build_upcoming_events_message(events):

    """Build alert message for upcoming economic events."""

    if not events:

        return None



    msg = chr(0x23f0) + " \u0647\u0634\u062f\u0627\u0631 \u0631\u0648\u06cc\u062f\u0627\u062f \u0627\u0642\u062a\u0635\u0627\u062f\u06cc\n"

    for ev in events:

        fa_title = _translate_event_title(ev["title"])

        if ev["minutes_away"] <= 0:

            status = chr(0x1f534) + " \u0627\u0644\u0627\u0646 \u062c\u0627\u0631\u06cc \u0627\u0633\u062a!"

        elif ev["minutes_away"] <= 30:

            status = chr(0x1f7e0) + f" {ev['minutes_away']} \u062f\u0642\u06cc\u0642\u0647 \u062f\u06cc\u06af\u0631"

        else:

            status = chr(0x1f7e2) + f" {ev['minutes_away']} \u062f\u0642\u06cc\u0642\u0647 \u062f\u06cc\u06af\u0631"



        msg += f"\n{chr(0x1f4c5)} {fa_title}\n"

        msg += f"   {status} | \u0648\u0642\u062a {ev['tehran_time']}\n"

        if ev.get("forecast"):

            msg += f"   \U0001f4ca \u067e\u06cc\u0634\u200c\u0628\u06cc\u0646\u06cc: {ev['forecast']} | \u0642\u0628\u0644\u06cc: {ev['previous']}\n"



    msg += "\n\U0001f4a1 \u0627\u0637\u0644\u0627\u0639\u0627\u062a \u0627\u0632 \u0628\u0627\u0632\u0627\u0631 \u0647\u0633\u062a\u0646\u062f."

    return msg




def _build_command_response(command):
    """Build a response for an interactive Telegram command."""
    command = command.split("@", 1)[0].strip().lower()

    if command in {"/start", "/help", "/راهنما"}:
        return None

    if command in {"/price", "/قیمت"}:
        data = fetch_bonbast_prices()
        if not data:
            return "⚠️ اطلاعات قیمت در دسترس نیست."
        usd_sell = int(data.get("usd1", 0))
        usd_buy = int(data.get("usd2", 0))
        gold = int(data.get("gold18", 0))
        btc_usd = float(data.get("bitcoin", 0))
        return (
            "💰 قیمت‌های لحظه‌ای\n\n"
            f"دلار فروش: {fmt(usd_sell)} تومان\n"
            f"دلار خرید: {fmt(usd_buy)} تومان\n"
            f"طلای ۱۸ عیار: {fmt(gold)} تومان\n"
            f"بیتکوین: ${fmt(btc_usd)}\n"
            f"بیتکوین به تومان: {fmt(round(btc_usd * usd_sell))} تومان"
        )

    if command in {"/analysis", "/تحلیل"}:
        fg = fetch_fear_greed()
        if not fg:
            return "⚠️ اطلاعات تحلیل در دسترس نیست."
        value = fg.get("value", 0)
        label = "طمع" if value > 50 else "ترس"
        return (
            "🧠 تحلیل بازار\n\n"
            f"شاخص ترس و طمع: {value}/100\n"
            f"وضعیت فعلی: {label}\n"
            f"میانگین ۷ روزه: {fg.get('avg_7d', '—')}\n"
            f"روند: {fg.get('trend', '—')}"
        )

    if command in {"/whales", "/نهنگ", "/نهنگها"}:
        whales = fetch_whale_unconfirmed()
        wallets = fetch_whale_wallets()
        prices = fetch_bonbast_prices() or {}
        btc_usd = float(prices.get("bitcoin", 0))
        return build_whale_message(whales, wallets, btc_usd) or "⚠️ اطلاعات نهنگ‌ها در دسترس نیست."


    return None


def poll_telegram_commands():
    """Process recent private commands without interfering with scheduled channel posts."""
    offset_file = os.environ.get("TELEGRAM_OFFSET_FILE", "telegram-command-offset.txt")
    try:
        with open(offset_file, "r", encoding="utf-8") as handle:
            offset = int(handle.read().strip())
    except (FileNotFoundError, ValueError):
        offset = 0

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 1, "allowed_updates": '["message"]'},
            timeout=5,
        )
        updates = response.json().get("result", [])
        for update in updates:
            offset = max(offset, update["update_id"] + 1)
            message = update.get("message", {})
            text = (message.get("text") or "").strip()
            chat_id = message.get("chat", {}).get("id")
            if not chat_id or not text.startswith("/"):
                continue
            response = _build_command_response(text.split()[0])
            if response:
                send_telegram(response, chat_id=chat_id)
        with open(offset_file, "w", encoding="utf-8") as handle:
            handle.write(str(offset))
    except Exception as exc:
        print(f"  Telegram command polling skipped: {exc}", file=sys.stderr)

def main():

    now = datetime.now()

    date_str = now.strftime("%Y-%m-%d %H:%M")



    # Set bot menu button to web app (runs once, harmless if repeated)
    set_bot_menu_button()

    poll_telegram_commands()

    # Cleanup yesterday's messages at start of each run

    cleanup_yesterday_messages()



    print(f"[{date_str}] Fetching all data...")



    bonbast = None

    fear_greed = None

    global_market = None

    whale_unconfirmed = None

    whale_wallets = None

    # === PARALLEL DATA FETCHING ===



    fetch_tasks = {



        "bonbast": fetch_bonbast_prices,



        "fear_greed": fetch_fear_greed,



        "global_market": fetch_global_market,



        "whale_unconfirmed": fetch_whale_unconfirmed,



        "whale_wallets": fetch_whale_wallets,

        "crypto_rsi": fetch_crypto_rsi_report,



    }



    results = {}



    errors = []



    with ThreadPoolExecutor(max_workers=8) as executor:



        future_map = {executor.submit(fn): name for name, fn in fetch_tasks.items()}



        for future in as_completed(future_map):



            name = future_map[future]



            try:



                results[name] = future.result()



                print(f"  [OK] {name}")



            except Exception as e:



                results[name] = None



                errors.append(f"{name}: {e}")



                print(f"  [ERR] {name}: {e}")







    bonbast = results.get("bonbast")



    fear_greed = results.get("fear_greed")



    global_market = results.get("global_market")



    whale_unconfirmed = results.get("whale_unconfirmed")



    whale_wallets = results.get("whale_wallets")

    crypto_rsi = results.get("crypto_rsi")

    if not bonbast:
        print(f"[{date_str}] WARN: No bonbast data. Retrying once...")
        try:
            bonbast = fetch_bonbast_prices()
            print(f"  [RETRY] bonbast: {'OK' if bonbast else 'FAILED'}")
        except Exception as e:
            print(f"  [RETRY] bonbast failed: {e}", file=sys.stderr)

    if not bonbast:
        print(f"[{date_str}] WARN: Bonbast unavailable, sending partial data...")
        # Still send independent messages
        rsi_msg = build_crypto_rsi_message(crypto_rsi)
        if rsi_msg:
            send_telegram(rsi_msg)
            print("  [SENT] Crypto RSI report")
        if whale_unconfirmed or whale_wallets:
            msg4 = build_whale_message(whale_unconfirmed, whale_wallets, 0)
            send_telegram(msg4)
            print(f"  [SENT] Whale tracker")
        if fear_greed:
            msg2 = f"🧠 آنالیز بازار جهانی\n"
            msg2 += f"{fear_greed['emoji']} شاخص ترس و طمع: {fear_greed['value']}/100\n"
            msg2 += f"   وضعیت: {fear_greed['classification']}\n"
            send_telegram(msg2)
            print(f"  [SENT] Fear & Greed")
        news = fetch_investing_news()
        if news:
            news_msg = build_news_message(news)
            if news_msg:
                send_telegram(news_msg)
                print(f"  [SENT] Breaking news")
        print(f"  [DONE] Partial run completed.")
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



    # Send the first message immediately; the remaining independent messages

    # are dispatched in parallel below so a slow API does not delay Telegram.

    send_telegram(msg1)

    print(f"  [SENT] Iran prices")


    # Iran stock market skipped - TSETMC is not accessible from GitHub Actions



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

    #  MESSAGE: Crypto RSI
    # ============================================================
    rsi_msg = build_crypto_rsi_message(crypto_rsi)
    if rsi_msg:
        send_telegram(rsi_msg)
        print("  [SENT] Crypto RSI report")

    # ============================================================

    #  MESSAGE 4: Enhanced Whale Tracker

    # ============================================================

    if whale_unconfirmed or whale_wallets:

        msg4 = build_whale_message(whale_unconfirmed, whale_wallets, btc_usd)

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

            if not os.path.exists(log_file):

                lines = []
            else:
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

        if not os.path.exists(log_file):

            lines = []
        else:
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

        bar_len = 12

        filled = int(fg["value"] / 100 * bar_len)

        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)

        fg_label = "\u0637\u0645\u0639" if fg["value"] > 50 else "\u062a\u0631\u0633"
        msg10 += f"{fg_label}: [{bar}] {fg['value']}/100\n\n"



        # Daily breakdown

        days_name = ["\u0634\u0646\u0628\u0647", "\u062c\u0645\u0639\u0647", "\u062f\u0648\u0634\u0646\u0628\u0646\u0647", "\u0633\u0647\u200c\u0634\u0646\u0628\u0647", "\u0686\u0647\u0627\u0631\u0634\u0646\u0628\u0647", "\u067e\u0646\u062c\u0634\u0646\u0628\u0647", "\u0627\u0645\u0631\u0648\u0632"]

        for i, val in enumerate(values_7d):

            if val <= 25:

                emoji = "\U0001f631"

            elif val <= 40:

                emoji = "\U0001f610"

            elif val <= 60:

                emoji = "\U0001f914"

            elif val <= 75:

                emoji = "\U0001f60f"

            else:

                emoji = "\U0001f929"

            msg10 += f"   {days_name[i]}: {val} {emoji}\n"



        msg10 += f"\n\u0645\u06cc\u0627\u0646\u06af\u06cc\u0646: {fg['avg_7d']}\n"

        msg10 += f"\u0628\u06cc\u0634\u062a\u0631\u06cc\u0646: {max_val}\n"

        msg10 += f"\u06a9\u0645\u062a\u0631\u06cc\u0646: {min_val}\n"

        msg10 += f"\u0646\u0648\u0633\u0627\u0646: {range_val} واحد\n\n"



        if fg["value"] > fg["avg_7d"]:

            msg10 += f"\U0001f4c8 \u0628\u0627\u0632\u0627\u0631 \u0637\u0645\u0639 \u0628\u06cc\u0634\u062a\u0631 \u0634\u062f\u0647 \u0627\u0633\u062a.\n"

        elif fg["value"] < fg["avg_7d"]:

            msg10 += f"\U0001f4c9 \u0628\u0627\u0632\u0627\u0631 \u062a\u0631\u0633 \u0628\u06cc\u0634\u062a\u0631 \u0634\u062f\u0647 \u0627\u0633\u062a.\n"

        else:

            msg10 += f"\u27a1\ufe0f \u0628\u0627\u0632\u0627\u0631 \u062a\u063a\u06cc\u06cc\u0631 \u0646\u06a9\u0631\u062f\u0647 \u0627\u0633\u062a.\n"



        if fg["value"] <= 25:

            msg10 += f"\n\U0001f4a1 \u062a\u0631\u0633 \u0634\u062f\u06cc\u062f = \u0645\u0648\u0642\u0639 \u062e\u0631\u06cc\u062f \u0628\u0631\u0627\u06cc \u0627\u0646\u062f\u0627\u0632\u0647 \u0628\u0644\u0646\u062f."

        elif fg["value"] >= 75:

            msg10 += f"\n\U0001f4a1 \u0637\u0645\u0639 \u0634\u062f\u06cc\u062f = \u0645\u0648\u0642\u0639 \u0641\u0631\u0648\u0634 \u0628\u0631\u0627\u06cc \u0627\u0646\u062f\u0627\u0632\u0647 \u0628\u0644\u0646\u062f."



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

                from datetime import datetime as _dt_now

                msg12 = "⏰ هشدار رویداد اقتصادی\n"

                for emoji, title, date_f, day_n, impact in high_events:

                    # Calculate time until event
                    try:

                        parts = date_f.split(" ")

                        time_part = parts[1] if len(parts) > 1 else date_f

                        date_part = parts[0] if len(parts) > 0 else ""

                        # Parse event time

                        event_dt = _dt_now.strptime(f"{date_part} {time_part}", "%Y/%m/%d %H:%M")

                        now_dt = _dt_now.now()

                        diff = event_dt - now_dt

                        mins = int(diff.total_seconds() / 60)

                        if mins > 0:

                            time_info = f"{mins} دقیقه دیگر | وقت {time_part}"

                        elif mins > -60:

                            time_info = f"{abs(mins)} دقیقه پیش | وقت {time_part}"

                        else:

                            time_info = f"وقت {time_part}"

                    except Exception:

                        time_info = f"وقت {date_f}"

                    # Format message

                    msg12 += f"📅 {title}\n"

                    msg12 += f"   {emoji} {time_info}\n"


                msg12 += "\n💡 اطلاعات از بازار هستند."

                send_telegram(msg12)

                print(f"  [SENT] Economic calendar")

            else:

                print(f"  [SKIP] No high impact USD events")

        except Exception as e:

            print(f"  [ERR] Calendar: {e}", file=sys.stderr)



    # ============================================================

    #  MESSAGE 13: Market Thermometer (combined 0-100)

    # ============================================================

    try:

        thermo_score = 50  # neutral default

        thermo_factors = []



        # Factor 1: Fear & Greed (weight 30%)

        if fear_greed:

            fg_val = fear_greed['value']

            thermo_score = thermo_score * 0.7 + fg_val * 0.3

            thermo_factors.append(f"F&G:{fg_val}")



        # Factor 2: BTC 7d change (weight 25%)

        try:

            s_cg = requests.Session()

            s_cg.verify = False

            r_cg = s_cg.get('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7', timeout=10)

            cg_data = r_cg.json()

            prices = cg_data.get('prices', [])

            if prices and len(prices) > 1:

                btc_7d_change = ((prices[-1][1] - prices[0][1]) / prices[0][1]) * 100

                # Map -20% to +20% -> 0 to 100

                btc_score = max(0, min(100, 50 + btc_7d_change * 2.5))

                thermo_score = thermo_score * 0.75 + btc_score * 0.25

                thermo_factors.append(f"BTC7d:{btc_7d_change:+.1f}%")

        except Exception:

            pass



        # Factor 3: Whale activity (weight 20%)

        if whale_unconfirmed:

            whale_count = len(whale_unconfirmed.get('whales', []))

            total_btc = whale_unconfirmed.get('total_whale_btc', 0)

            if total_btc > 5000:

                whale_score = 80  # heavy selling

            elif total_btc > 1000:

                whale_score = 65

            elif whale_count > 3:

                whale_score = 55

            else:

                whale_score = 50

            thermo_score = thermo_score * 0.8 + whale_score * 0.2

            thermo_factors.append(f"Whale:{whale_count}")



        thermo_score = int(round(thermo_score))



        # Status description

        if thermo_score >= 80:

            thermo_status = "\U0001f525 \u062f\u0627\u063a \u0634\u062f\u0647 - \u0637\u0645\u0639 \u0634\u062f\u06cc\u062f"

        elif thermo_score >= 65:

            thermo_status = "\U0001f525 \u06af\u0631\u0645 - \u0637\u0645\u0639\u06cc \u0627\u0632 \u062d\u062f"

        elif thermo_score >= 45:

            thermo_status = "\u27a1\ufe0f \u0646\u0631\u0645\u0627\u0644 - \u062a\u0639\u0627\u062f\u0644"

        elif thermo_score >= 25:

            thermo_status = "\U0001f4c9 \u0633\u0631\u062f - \u062a\u0631\u0633\u06cc \u0627\u0632 \u062d\u062f"

        else:

            thermo_status = "\u2744\ufe0f \u0633\u0631\u062f \u0634\u062f\u0647 - \u062a\u0631\u0633 \u0634\u062f\u06cc\u062f"



        # Visual bar

        bar_len = 12

        filled = int(thermo_score / 100 * bar_len)

        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)



        msg13 = f"\U0001f321\ufe0f \u062f\u0645\u0627\u0633\u0646\u062c \u0628\u0627\u0632\u0627\u0631\n\n"

        msg13 += f"  [{bar}] {thermo_score}/100\n\n"

        msg13 += f"  {thermo_status}\n\n"

        msg13 += f"\U0001f4ca \u062c\u0632\u0626\u06cc\u0627\u062a:\n"

        msg13 += f"   \u2022 {' | '.join(thermo_factors)}\n\n"

        msg13 += f"\U0001f4a1 \u0637\u0645\u0639 \u0634\u062f\u06cc\u062f = \u0645\u0648\u0642\u0639 \u0641\u0631\u0648\u0634 \u0627\u062d\u062a\u0645\u0627\u0644\u06cc\n"

        msg13 += f"\U0001f4a1 \u062a\u0631\u0633 \u0634\u062f\u06cc\u062f = \u0645\u0648\u0642\u0639 \u062e\u0631\u06cc\u062f \u0627\u062d\u062a\u0645\u0627\u0644\u06cc"



        send_telegram(msg13)

        print(f"  [SENT] Market thermometer")

    except Exception as e:

        print(f"  [ERR] Thermometer: {e}", file=sys.stderr)



    # ============================================================

    #  MESSAGE 14: Smart Buy/Sell Signal

    # ============================================================

    try:

        signals = []

        score = 0  # -100 to +100



        # Signal 1: Fear & Greed

        if fear_greed:

            fg_val = fear_greed['value']

            if fg_val <= 25:

                signals.append(("\U0001f7e2 \u062e\u0631\u06cc\u062f", f"\u062a\u0631\u0633 \u0634\u062f\u06cc\u062f ({fg_val}/100)"))

                score += 30

            elif fg_val >= 75:

                signals.append(("\U0001f534 \u0641\u0631\u0648\u0634", f"\u0637\u0645\u0639 \u0634\u062f\u06cc\u062f ({fg_val}/100)"))

                score -= 30

            else:

                signals.append(("\U0001f7e1 \u0635\u0628\u0631", f"\u0648\u0636\u0639\u06cc\u062a: {fg_val}/100"))

                score += 0



        # Signal 2: BTC trend

        try:

            s_cg = requests.Session()

            s_cg.verify = False

            r_cg = s_cg.get('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7', timeout=10)

            cg_data = r_cg.json()

            prices = cg_data.get('prices', [])

            if prices and len(prices) > 1:

                btc_7d = ((prices[-1][1] - prices[0][1]) / prices[0][1]) * 100

                if btc_7d > 10:

                    signals.append(("\U0001f4c8 \u0631\u0648\u0646\u062f \u0642\u0648\u06cc", f"BTC +{btc_7d:.1f}% \u062f\u0631 7 \u0631\u0648\u0632"))

                    score += 25

                elif btc_7d < -10:

                    signals.append(("\U0001f4c9 \u0631\u0648\u0646\u062f \u0636\u0639\u06cc\u0641", f"BTC {btc_7d:.1f}% \u062f\u0631 7 \u0631\u0648\u0632"))

                    score -= 25

                else:

                    signals.append(("\u27a1\ufe0f", f"\u0631\u0648\u0646\u062f \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646: \u062e\u0646\u062b\u06cc؛ {btc_7d:+.1f}% \u062f\u0631 ۷ \u0631\u0648\u0632"))

        except Exception:

            pass



        # Signal 3: Whale activity

        if whale_unconfirmed:

            total_btc = whale_unconfirmed.get('total_whale_btc', 0)

            whale_count = len(whale_unconfirmed.get('whales', []))

            if total_btc > 5000:

                signals.append(("\U0001f4c9 \u0646\u0647\u0646\u06af\u0647\u0627 \u0641\u0631\u0648\u0634\u0646\u0646\u062f\u0647", f"{fmt(total_btc)} BTC \u062f\u0631 \u0631\u0627\u0647 \u0641\u0631\u0648\u0634"))

                score -= 20

            elif whale_count > 3:

                signals.append(("\U0001f4c8 \u0646\u0647\u0646\u06af\u0647\u0627 \u062e\u0631\u06cc\u062f\u0627\u0631", f"{whale_count} \u062a\u0631\u0627\u06a9\u0646\u0634 \u0628\u0632\u0631\u06af"))

                score += 15

            else:

                signals.append(("\u2705", f"\u0641\u0639\u0627\u0644\u06cc\u062a \u0646\u0647\u0646\u06af\u200c\u0647\u0627: \u0622\u0631\u0627\u0645؛ {whale_count} \u062a\u0631\u0627\u06a9\u0646\u0634 \u0628\u0632\u0631\u06af"))



        # Signal 4: Iran gold premium

        iran_gold_oz = gold * 31.1

        intl_gold_oz = ounce_usd * usd_sell

        if intl_gold_oz > 0:

            premium = ((iran_gold_oz - intl_gold_oz) / intl_gold_oz * 100)

            if premium > 10:

                signals.append(("\U0001f4a1 \u0637\u0644\u0627 \u06af\u0631\u0627\u0646", f"\u0627\u06cc\u0631\u0627\u0646 {premium:.0f}% \u06af\u0631\u0627\u0646\u062a\u0631"))

                score -= 10

            elif premium < -3:

                signals.append(("\U0001f4a1", f"\u0645\u0642\u0627\u06cc\u0633\u0647 \u0637\u0644\u0627: \u0627\u06cc\u0631\u0627\u0646 {abs(premium):.0f}% \u0627\u0631\u0632\u0627\u0646\u200c\u062a\u0631؛ \u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u0628\u0631\u0631\u0633\u06cc \u0628\u06cc\u0634\u062a\u0631"))

                score += 10



        # Final signal

        score = max(-100, min(100, score))

        if score >= 30:

            final = "\U0001f7e2 \u0633\u06cc\u06af\u0646\u0627\u0644 \u062e\u0631\u06cc\u062f"

            final_emoji = "\U0001f7e2"

        elif score <= -30:

            final = "\U0001f534 \u0633\u06cc\u06af\u0646\u0627\u0644 \u0641\u0631\u0648\u0634"

            final_emoji = "\U0001f534"

        else:

            final = "\U0001f7e1 \u0633\u06cc\u06af\u0646\u0627\u0644 \u0635\u0628\u0631"

            final_emoji = "\U0001f7e1"



        msg14 = f"\U0001f9ed \u062a\u062d\u0644\u06cc\u0644 \u0628\u0627\u0632\u0627\u0631: \u067e\u06cc\u0634\u0646\u0647\u0627\u062f \u0635\u0628\u0631\n\n"

        msg14 += f"{final_emoji} \u0648\u0636\u0639\u06cc\u062a \u06a9\u0644\u06cc: \u062e\u0646\u062b\u06cc\n" if -30 < score < 30 else f"{final_emoji} {final}\n"

        msg14 += f"\U0001f4ca \u0627\u0645\u062a\u06cc\u0627\u0632 \u06a9\u0644\u06cc: {score:+d} \u0627\u0632 100\n\n"

        for emoji, desc in signals:

            msg14 += f"• {desc}\n"

        msg14 += f"\n\u26a0\ufe0f \u0627\u06cc\u0646 \u067e\u06cc\u0627\u0645 \u062a\u0648\u0635\u06cc\u0647 \u0645\u0627\u0644\u06cc \u0646\u06cc\u0633\u062a؛ \u067e\u06cc\u0634 \u0627\u0632 \u0645\u0639\u0627\u0645\u0644\u0647 \u062f\u0627\u062f\u0647\u200c\u0647\u0627 \u0648 \u0645\u0646\u0627\u0628\u0639 \u0631\u0627 \u0628\u0631\u0631\u0633\u06cc \u06a9\u0646\u06cc\u062f."



        send_telegram(msg14)

        print(f"  [SENT] Buy/Sell signal")

    except Exception as e:

        print(f"  [ERR] Signal: {e}", file=sys.stderr)



    # ============================================================

    #  MESSAGE 15: DXY (US Dollar Index)

    # ============================================================

    try:

        s_fx = requests.Session()

        s_fx.verify = False

        r_fx = s_fx.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=10)

        fx_data = r_fx.json()

        rates = fx_data.get('rates', {})



        eur = rates.get('EUR', 0)

        jpy = rates.get('JPY', 0)

        gbp = rates.get('GBP', 0)

        cad = rates.get('CAD', 0)

        sek = rates.get('SEK', 0)

        chf = rates.get('CHF', 0)



        # Correct DXY calculation

        # API returns USD/base (e.g. EUR=0.857 means 1 USD=0.857 EUR)

        # DXY formula needs: EUR/USD, USD/JPY, GBP/USD, USD/CAD, USD/SEK, USD/CHF

        if eur and jpy and gbp:

            eur_usd = 1.0 / eur   # e.g. 1/0.857 = 1.167

            gbp_usd = 1.0 / gbp   # e.g. 1/0.733 = 1.364

            dxy = 50.14348112 * (eur_usd ** -0.576) * (jpy ** 0.136) * (gbp_usd ** -0.119) * (cad ** 0.091) * (sek ** 0.042) * (chf ** 0.036)

            dxy = round(dxy, 2)



            # Determine trend

            if dxy > 105:

                dxy_status = "\U0001f4c8 \u062f\u0644\u0627\u0631 \u0642\u0648\u06cc \u0627\u0633\u062a - \u0641\u0636\u0631 \u0628\u0631 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646"

            elif dxy < 99:

                dxy_status = "\U0001f4c9 \u062f\u0644\u0627\u0631 \u0636\u0639\u06cc\u0641 \u0627\u0633\u062a - \u062d\u0645\u0627\u06cc\u062a \u0628\u0631 \u0637\u0644\u0627 \u0648 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646"

            else:

                dxy_status = "\u27a1\ufe0f \u062f\u0644\u0627\u0631 \u0646\u0631\u0645\u0627\u0644 - \u062a\u0627\u062b\u06cc\u0631 \u0645\u062a\u0648\u0633\u0637"



            # USD to IRR proxy (from bonbast)

            msg15 = f"\U0001f310 \u0634\u0627\u062e\u0635 \u062f\u0644\u0627\u0631 (DXY)\n\n"

            msg15 += f"   DXY: {dxy}\n"

            msg15 += f"   {dxy_status}\n\n"

            msg15 += f"\U0001f4b1 \u0646\u0631\u062e \u0627\u0631\u0632:\n"

            msg15 += f"   EUR: {eur} | GBP: {gbp}\n"

            msg15 += f"   JPY: {jpy} | CHF: {chf}\n\n"

            msg15 += f"\U0001f4a1 \u062f\u0644\u0627\u0631 \u0642\u0648\u06cc\u062a\u0631 = \u0637\u0644\u0627 \u0648 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 \u0636\u0639\u06cc\u0641\u062a\u0631"

            msg15 += f"\U0001f4a1 \u062f\u0644\u0627\u0631 \u0636\u0639\u06cc\u0641\u062a\u0631 = \u0637\u0644\u0627 \u0648 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 \u0642\u0648\u06cc\u062a\u0631"



            send_telegram(msg15)

            print(f"  [SENT] DXY")

        else:

            print(f"  [SKIP] DXY: missing FX rates")

    except Exception as e:

        print(f"  [ERR] DXY: {e}", file=sys.stderr)



    # ============================================================

    #  MESSAGE 16: Exchange Inflow/Outflow (using CoinGecko)

    # ============================================================

    try:

        s_ex = requests.Session()

        s_ex.verify = False



        # Get exchange data from CoinGecko

        r_ex = s_ex.get('https://api.coingecko.com/api/v3/exchanges?per_page=5&page=1', timeout=10)

        # The free API can return an error object, rate-limit response, or an empty payload.
        # Never treat that response as exchange data or fail the whole run.
        exchanges = []
        if r_ex.ok:

            try:

                payload = r_ex.json()

                if isinstance(payload, list):

                    exchanges = [item for item in payload if isinstance(item, dict)]

                elif isinstance(payload, dict):

                    nested = payload.get('data', payload.get('exchanges', []))

                    if isinstance(nested, list):

                        exchanges = [item for item in nested if isinstance(item, dict)]

            except (ValueError, TypeError):

                exchanges = []



        if exchanges:

            msg16 = f"\U0001f3e6 \u062a\u063a\u06cc\u06cc\u0631\u0627\u062a \u0635\u0631\u0627\u0641\u06cc\u200c\u0647\u0627\n\n"



            # Top exchanges by volume

            for ex in exchanges[:5]:

                name = ex.get('name', '?')

                vol_24h = ex.get('trade_volume_24h_btc', 0)

                rank = ex.get('trust_score_rank', '?')

                msg16 += f"   #{rank} {name}: {fmt(round(vol_24h))} BTC\n"



            # BTC supply on exchanges trend

            msg16 += f"\n\U0001f4ca \u062c\u0632\u0626\u06cc\u0627\u062a:\n"

            msg16 += f"   \u062d\u062c\u0645 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 \u062f\u0631 \u0635\u0631\u0627\u0641\u06cc\u200c\u0647\u0627:\n"



            total_btc = sum(ex.get('trade_volume_24h_btc', 0) for ex in exchanges)

            msg16 += f"   \u06a9\u0644: ~{fmt(round(total_btc))} BTC\n"



            # Estimate inflow/outflow from volume

            avg_vol = total_btc / len(exchanges) if exchanges else 0

            if total_btc > 2000000:

                msg16 += f"   \U0001f4c9 \u062d\u062c\u0645 \u0648\u0631\u0648\u062f\u06cc \u0628\u0647 \u0635\u0631\u0627\u0641\u06cc \u0632\u06cc\u0627\u062f \u0627\u0633\u062a - \u0627\u062d\u062a\u0645\u0627\u0644 \u0641\u0631\u0648\u0634"

            elif total_btc < 500000:

                msg16 += f"   \U0001f4c8 \u062d\u062c\u0645 \u062e\u0631\u0648\u062c \u0627\u0632 \u0635\u0631\u0627\u0641\u06cc \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a - \u0627\u062d\u062a\u0645\u0627\u0644 \u0646\u06af\u0647\u062f\u0627\u0631\u06cc"

            else:

                msg16 += f"   \u27a1\ufe0f \u0639\u0627\u062f\u06cc"



            send_telegram(msg16)

            print(f"  [SENT] Exchange flow")

        else:

            print("  [SKIP] Exchange flow: data unavailable")

    except Exception as e:

        print(f"  [WARN] Exchange flow skipped: {e}", file=sys.stderr)


    # ============================================================

    #  MESSAGE 17: BTC/Gold Ratio

    # ============================================================

    try:

        if ounce_usd > 0 and btc_usd > 0:

            btc_gold_ratio = btc_usd / ounce_usd

            gold_per_btc_gram = btc_usd / (gold / usd_sell) if gold > 0 else 0



            msg17 = f"\U0001f4b0 \u0646\u0633\u0628\u062a \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 / \u0637\u0644\u0627\n\n"

            msg17 += f"   \u06cc\u06a9 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 = {btc_gold_ratio:.2f} \u0627\u0646\u0633 \u0637\u0644\u0627\n"

            msg17 += f"   \u06cc\u06a9 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 = {fmt(round(gold_per_btc_gram))} \u06af\u0631\u0645 \u0637\u0644\u0627\n\n"

            msg17 += f"\U0001f4ca \u0645\u0642\u0627\u06cc\u0633\u0647 \u0647\u0645\u0628\u0633\u062a\u06af\u06cc:\n"



            if btc_gold_ratio > 40:

                msg17 += f"   \U0001f4c8 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 \u0646\u0633\u0628\u062a \u0628\u0647 \u0637\u0644\u0627 \u062f\u0631 \u0631\u0633\u06cc\u062f\u0646 \u0627\u0633\u062a\n"

            elif btc_gold_ratio < 25:

                msg17 += f"   \U0001f4c9 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 \u0627\u0631\u0632\u0627\u0646\u062a\u0631 \u0627\u0632 \u0637\u0644\u0627 \u0627\u0633\u062a\n"

            else:

                msg17 += f"   \u27a1\ufe0f \u0646\u0633\u0628\u062a \u0646\u0631\u0645\u0627\u0644\u06cc\n"



            msg17 += f"\n\U0001f4a1 \u0627\u06af\u0631 \u0628\u06cc\u062a\u06a9\u0648\u06cc\u0646 \u0632\u0648\u062f\u062a\u0631 \u0627\u0632 \u0637\u0644\u0627 \u0631\u0634\u062f \u06a9\u0646\u062f\u060c \u0628\u0647\u062a\u0631 \u0627\u0633\u062a"



            send_telegram(msg17)

            print(f"  [SENT] BTC/Gold ratio")

    except Exception as e:

        print(f"  [ERR] BTC/Gold: {e}", file=sys.stderr)



    

    # ============================================================

    #  MESSAGE 18: Breaking News (Investing.com)

    # ============================================================

    try:

        news_list = fetch_investing_news()

        if news_list:

            news_msg = build_news_message(news_list)

            if news_msg:

                send_telegram(news_msg)

                print(f"  [SENT] Breaking news")

    except Exception as e:

        print(f"  [ERR] News: {e}", file=sys.stderr)



    # ============================================================

    #  MESSAGE 19: Upcoming Economic Events Alert

    # ============================================================

    try:

        upcoming = fetch_upcoming_events()

        if upcoming:

            upcoming_msg = build_upcoming_events_message(upcoming)

            if upcoming_msg:

                send_telegram(upcoming_msg)

                print(f"  [SENT] Upcoming events alert")

    except Exception as e:

        print(f"  [ERR] Upcoming events: {e}", file=sys.stderr)



# ============================================================

    #  LOG

    # ============================================================

    log_file = os.path.join(os.path.expanduser("~"), "dollar-price-log.txt")

    log_entry = f"[{date_str}] USD:{fmt(usd_sell)}/{fmt(usd_buy)} | Gold:{fmt(gold)} | BTC:${fmt(btc_usd)}"

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



    # Save prices.json for dashboard
    try:
        prices = {
            "timestamp": date_str,
            "usd_sell": usd_sell if 'usd_sell' in dir() else 0,
            "usd_buy": usd_buy if 'usd_buy' in dir() else 0,
            "gold_18k": gold if 'gold' in dir() else 0,
            "btc_usd": btc_usd if 'btc_usd' in dir() else 0,
            "fear_greed": fear_greed.get("value", 0) if fear_greed else 0,
            "btc_dominance": global_market.get("btc_dominance", 0) if global_market else 0,
            "market_cap": global_market.get("total_market_cap_t", 0) * 1e12 if global_market else 0,
            "market_volume": global_market.get("total_volume_t", 0) * 1e12 if global_market else 0,
            "market_change": global_market.get("market_cap_change_24h", 0) if global_market else 0,
            "top10": []
        }
        top10_data = globals().get('_TOP10_COINS', [])
        if top10_data:
            for c in top10_data[:10]:
                prices["top10"].append({
                    "symbol": c.get("symbol", ""),
                    "price": c.get("current_price", 0),
                    "change_24h": c.get("price_change_percentage_24h", 0),
                    "market_cap": c.get("market_cap", 0),
                })
        import json as _json
        with open("prices.json", "w", encoding="utf-8") as f:
            _json.dump(prices, f, ensure_ascii=False, indent=2)
        print(f"[{date_str}] Saved prices.json")
    except Exception as e:
        print(f"[{date_str}] prices.json error: {e}", file=sys.stderr)

    print(f"[{date_str}] All done! ({len(errors)} errors)")





if __name__ == "__main__":

    main()

