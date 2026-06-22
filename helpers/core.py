"""Core publishing loop: fetch news and send them to Telegram."""

import logging
from datetime import datetime, timedelta

import emoji

from . import bot
from . import config
from . import database
from .feeds import parse_news
from .translation import translate_text


# Main code
def main():
    """Main robot code"""
    logging.info("Starting bot")
    # Track how many news we sent
    news_cnt: int = 0
    max_news = config.get_max_news_cnt_from_env()
    # Get SQL cursor
    sql_connector = database.get_sql_connector()
    # Clean data from DB
    feeds_from_db = [x[0] for x in sql_connector.cursor().execute("SELECT url FROM feeds WHERE 1").fetchall()]
    if feeds_from_db is None:
        logging.error("No news from DB")
        sql_connector.close()
        return
    logging.debug("Fetching [" + str(len(feeds_from_db)) + "] feeds")
    # Monitor exceptions and report in case of multiple errors
    exception_cnt = 0
    exception_message = ""
    # Get news from feed
    for single_news in parse_news(feeds_from_db):
        # Check if we already sent this message
        if sql_connector.cursor().execute("SELECT * FROM news WHERE checksum='" + single_news.checksum + "'").fetchone() is None:
            logging.info("Sending: [" + single_news.link + "]")
            # Check if article is no more than 30 days
            if datetime.now().replace(tzinfo=None) - single_news.date.replace(tzinfo=None) > timedelta(days=30):
                logging.debug("Article: [" + single_news.link + "] is older than 30 days, skipping")
            elif single_news.date.replace(tzinfo=None) > datetime.now().replace(tzinfo=None):
                logging.warning("Article: [" + single_news.link + "] is coming from the future?!")
            else:
                # Prepare message to send
                emoji_flag_it = emoji.emojize(":Italy:", language="alias")
                emoji_flag_en = emoji.emojize(":United_States:", language="alias")
                emoji_pencil = emoji.emojize(":pencil2:", language="alias")
                emoji_calendar = emoji.emojize(":spiral_calendar:", language="alias")
                emoji_link = emoji.emojize(":link:", language="alias")
                try:
                    telegram_payload = f"{emoji_flag_it} {translate_text(single_news.title, 'it')}\n" + \
                                        f"{emoji_flag_en} {translate_text(single_news.title, 'en')}\n" + \
                                        f"\n{emoji_pencil} {single_news.author}\n" + \
                                        f"{emoji_calendar} {single_news.date.strftime('%Y/%m/%d, %H:%M')}\n" + \
                                        f"\n{emoji_flag_it} {translate_text(single_news.summary, 'it')}\n" + \
                                        f"\n{emoji_flag_en} {translate_text(single_news.summary, 'en')}\n" + \
                                        f"\n{emoji_link} {single_news.link}"
                    if not config.dry_run:
                        bot.telegram_bot.send_message(config.get_target_chat_from_env(), telegram_payload, parse_mode="MARKDOWN")
                    else:
                        logging.info(telegram_payload)
                    if not config.dry_run:
                        # Store this article to DB
                        logging.debug("Adding [" + single_news.checksum + "] to store")
                        sql_connector.cursor().execute("INSERT INTO news(date, checksum) VALUES(?, ?)", [single_news.date, single_news.checksum])
                        sql_connector.commit()
                    news_cnt += 1
                except Exception as returned_exception:
                    exception_message = str(returned_exception)
                    logging.error(exception_message)
                    if "can\'t parse entities:" in exception_message:
                        logging.warning("Skipping [" + single_news.checksum + "] due to Telegram parsing error")
                        sql_connector.cursor().execute("INSERT INTO news(date, checksum) VALUES(?, ?)", [single_news.date, single_news.checksum])
                        sql_connector.commit()
                    else:
                        exception_cnt += 1
        # This message was already posted
        else:
            logging.debug("Post at [" + single_news.link + "] was already sent")
        # Check errors count
        if exception_cnt > 3:
            logging.error("Too many errors, skipping this upgrade")
            if not config.dry_run:
                bot.telegram_bot.send_message(config.get_admin_chat_from_env(), "Too many errors, skipping this execution. Last error: `" + exception_message + "`")
            break
        # Stop execution after sending x elements
        if news_cnt >= max_news:
            break
    logging.debug("No more articles to process, waiting for next execution")
    # Close DB connection
    sql_connector.close()
