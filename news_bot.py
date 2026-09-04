import feedparser
import time
import hashlib
import os
import socket
from datetime import datetime
from deep_translator import GoogleTranslator
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Таймаут на сетевые запросы
socket.setdefaulttimeout(15)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

NEWS_PER_SOURCE = 2

FEEDS = {
    "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition_world.rss",
    "Reuters": "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    "AP": "https://feedx.net/rss/ap.xml",
}

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Не указаны BOT_TOKEN или CHAT_ID")

bot = telebot.TeleBot(BOT_TOKEN)
translator = GoogleTranslator(source="en", target="ru")

def translate_text(text: str) -> str:
    try:
        return translator.translate(text[:500])
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return text

def create_read_button(url: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Читать →", url=url))
    return markup

def fetch_headlines():
    items = []

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

                title_ru = translate_text(title)
                items.append({
                    "source": source,
                    "title": title_ru,
                    "link": link,
                })
                count += 1
                time.sleep(0.3)

        except Exception as e:
            print(f"Ошибка {source}: {e}")

    return items

def send_news(items):
    if not items:
        print("Новых новостей нет")
        bot.send_message(CHAT_ID, "ℹ️ Сейчас свежих заголовков нет")
        return

    header = f"📰 <b>Свежие заголовки</b>\n{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    bot.send_message(CHAT_ID, header, parse_mode="HTML")

    for item in items:
        text = f"<b>{item['source']}</b>\n\n{item['title']}"
        markup = create_read_button(item["link"])
        try:
            bot.send_message(
                CHAT_ID,
                text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True
            )
            time.sleep(0.4)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    print(f"Отправлено {len(items)} новостей")

if __name__ == "__main__":
    print("Запуск сбора новостей...")
    news = fetch_headlines()
    send_news(news)
    print("Готово.")
