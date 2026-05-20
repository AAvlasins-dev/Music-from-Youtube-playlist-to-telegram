import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot, error as tg_error
from telegram.ext import ApplicationBuilder
from googleapiclient.discovery import build

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_PLAYLIST_ID = os.getenv("YOUTUBE_PLAYLIST_ID")

SENT_VIDEOS_FILE = "sent_videos.json"
PINNED_MSGS_FILE = "pinned_msgs.json"


def load_json(path: str) -> dict | list:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_playlist_videos(playlist_id: str) -> list[dict]:
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    videos = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        )
        response = request.execute()

        for item in response.get("items", []):
            video_id = item["contentDetails"]["videoId"]
            title = item["snippet"]["title"]
            published_at = item["snippet"]["publishedAt"]
            videos.append(
                {"id": video_id, "title": title, "published_at": published_at}
            )

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


async def post_new_videos() -> None:
    sent_videos: dict = load_json(SENT_VIDEOS_FILE)
    pinned_msgs: dict = load_json(PINNED_MSGS_FILE)

    bot = Bot(token=TELEGRAM_TOKEN)
    videos = get_playlist_videos(YOUTUBE_PLAYLIST_ID)

    new_videos = [v for v in videos if v["id"] not in sent_videos]
    if not new_videos:
        logger.info("No new videos to post.")
        return

    for video in new_videos:
        url = f"https://www.youtube.com/watch?v={video['id']}"
        text = f"🎵 *{video['title']}*\n\n{url}"

        try:
            message = await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode="Markdown",
            )
            sent_videos[video["id"]] = {
                "title": video["title"],
                "message_id": message.message_id,
                "posted_at": datetime.utcnow().isoformat(),
            }
            logger.info("Posted: %s", video["title"])

            # pin the latest message
            if pinned_msgs.get("last_message_id"):
                try:
                    await bot.unpin_chat_message(
                        chat_id=CHANNEL_ID,
                        message_id=pinned_msgs["last_message_id"],
                    )
                except tg_error.TelegramError as e:
                    logger.warning("Could not unpin previous message: %s", e)

            await bot.pin_chat_message(
                chat_id=CHANNEL_ID,
                message_id=message.message_id,
                disable_notification=True,
            )
            pinned_msgs["last_message_id"] = message.message_id

        except tg_error.TelegramError as e:
            logger.error("Failed to post %s: %s", video["id"], e)

    save_json(SENT_VIDEOS_FILE, sent_videos)
    save_json(PINNED_MSGS_FILE, pinned_msgs)


if __name__ == "__main__":
    import asyncio

    asyncio.run(post_new_videos())
