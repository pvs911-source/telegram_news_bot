import feedparser
import time
import hashlib
import os
import re
import socket
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

socket.setdefaulttimeout(20)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

NEWS_PER_SOURCE = 3

FEEDS = {
    "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition_world.rss",
    "Reuters": "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    "AP": "https://feedx.net/rss/ap.xml",
}

SEEN_FILE = "seen_news.txt"

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Не указаны BOT_TOKEN или CHAT_ID")

bot = telebot.TeleBot(BOT_TOKEN)


def is_mostly_russian(text: str) -> bool:
    if not text:
        return False
    rus = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return rus > 0 and rus >= lat


def translate_text(text: str) -> str:
    """Пробует несколько переводчиков, пока не получится."""
    text = (text or "").strip()
    if not text:
        return text

    if is_mostly_russian(text):
        return text

    src = text[:450]

    # --- 1) deep-translator (Google) ---
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source="auto", target="ru").translate(src)
        if result and result.strip() and not is_mostly_russian(src) and is_mostly_russian(result):
            print(f"OK Google: {src[:40]} -> {result[:40]}")
            return result.strip()
        if result and result.strip() and result.strip() != src:
            print(f"OK Google (soft): {result[:40]}")
            return result.strip()
    except Exception as e:
        print(f"Google fail: {e}")

    # --- 2) translators: Bing ---
    try:
        import translators as ts
        result = ts.translate_text(src, translator="bing", from_language="en", to_language="ru")
        if result and result.strip() and result.strip() != src:
            print(f"OK Bing: {result[:40]}")
            return result.strip()
    except Exception as e:
        print(f"Bing fail: {e}")

    # --- 3) translators: Yandex ---
    try:
        import translators as ts
        result = ts.translate_text(src, translator="yandex", from_language="en", to_language="ru")
        if result and result.strip() and result.strip() != src:
            print(f"OK Yandex-ts: {result[:40]}")
            return result.strip()
    except Exception as e:
        print(f"Yandex-ts fail: {e}")

    # --- 4) yandexfreetranslate ---
    try:
        from yandexfreetranslate import YandexFreeTranslate
        for api_name in ("web", "ios"):
            try:
                result = YandexFreeTranslate(api=api_name).translate("en", "ru", src)
                if result and result.strip() and result.strip() != src:
                    print(f"OK YandexFree({api_name}): {result[:40]}")
                    return result.strip()
            except Exception as e:
                print(f"YandexFree({api_name}) fail: {e}")
                time.sleep(0.3)
    except Exception as e:
        print(f"YandexFree import fail: {e}")

    print(f"NO TRANSLATE: {src[:60]}")
    return text


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in list(seen)[-500:]:
            f.write(item + "\n")


def get_news_id(title, link):
    return hashlib.md5((title + link).encode()).hexdigest()


def create_read_button(url: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Читать →", url=url))
    return markup


def fetch_headlines():
    seen = load_seen()
    new_items = []

    for source, url in FEEDS.items():
        print(f"Читаю {source}...")
        try:
            feed = feedparser.parse(url)
            count = 0

            for entry in feed.entries:
                if count >= NEWS_PER_SOURCE:
                    break

                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()

                if not title or not link:
                    continue

                news_id = get_news_id(title, link)
                if news_id in seen:
                    continue

                title_ru = translate_text(title)
                time.sleep(0.6)  # пауза, чтобы переводчики не резали

                new_items.append({
                    "source": source,
                    "title": title_ru,
                    "link": link,
                    "id": news_id,
                })
                seen.add(news_id)
                count += 1

        except Exception as e:
            print(f"Ошибка {source}: {e}")

    save_seen(seen)
    return new_items


def send_news(items):
    if not items:
        print("Новых новостей нет")
        return

    header = f"📰 <b>Свежие заголовки</b>\n{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    bot.send_message(CHAT_ID, header, parse_mode="HTML")

    for item in items:
        text = (
            f"<b>{item['source']}</b>\n\n"
            f"{item['title']}\n\n"
            f"<a href=\"{item['link']}\">Читать новость</a>"
        )
        markup = create_read_button(item["link"])

        try:
            bot.send_message(
                CHAT_ID,
                text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True,
            )
            time.sleep(0.4)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    print(f"Отправлено {len(items)} новостей")


if __name__ == "__main__":
    print("Запуск сбора новостей...")
    items = fetch_headlines()
    send_news(items)
    print("Готово.")
