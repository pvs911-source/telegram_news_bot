import feedparser
import time
import hashlib
import os
from datetime import datetime
from deep_translator import GoogleTranslator
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

NEWS_PER_SOURCE = 3
INTERVAL = 3600  # 1 час

FEEDS = {
    "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition_world.rss",
    "Reuters": "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    "AP": "https://feedx.net/rss/ap.xml",
}

SEEN_FILE = "seen_news.txt"
# ==============================================

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Не указаны BOT_TOKEN или CHAT_ID")

bot = telebot.TeleBot(BOT_TOKEN)
translator = GoogleTranslator(source='en', target='ru')

def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in list(seen)[-800:]:
            f.write(item + "\n")

def get_news_id(title, link):
    return hashlib.md5((title + link).encode()).hexdigest()

def translate_text(text: str) -> str:
    try:
        return translator.translate(text)
    except Exception:
        return text

def create_read_button(url: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Читать →", url=url))
    return markup

def fetch_headlines():
    seen = load_seen()
    new_items = []

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0

            for entry in feed.entries:
                if count >= NEWS_PER_SOURCE:
                    break

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()

                if not title or not link:
                    continue

                news_id = get_news_id(title, link)
                if news_id in seen:
                    continue

                title_ru = translate_text(title)

                new_items.append({
                    "source": source,
                    "title": title_ru,
                    "link": link,
                    "id": news_id
                })
                seen.add(news_id)
                count += 1

        except Exception as e:
            print(f"[{datetime.now()}] Ошибка {source}: {e}")

    save_seen(seen)
    return new_items

def send_news(items):
    if not items:
        print(f"[{datetime.now()}] Новых новостей нет")
        return

    header = f"📰 <b>Свежие заголовки</b>\n{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    bot.send_message(CHAT_ID, header, parse_mode="HTML")

    for item in items:
        text = f"<b>{item['source']}</b>\n\n{item['title']}"
        markup = create_read_button(item['link'])

        try:
            bot.send_message(
                CHAT_ID,
                text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    print(f"[{datetime.now()}] Отправлено {len(items)} новостей")

def main():
    print("Бот запущен на сервере...")
    while True:
        try:
            items = fetch_headlines()
            send_news(items)
        except Exception as e:
            print(f"[{datetime.now()}] Критическая ошибка: {e}")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
