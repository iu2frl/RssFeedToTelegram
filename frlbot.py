# Import external classes
import feedparser
import dateutil.parser
import telebot
import logging
import os
from datetime import datetime, timedelta
import re
import hashlib
import sqlite3
import schedule
import time
import sys
import getopt
import threading
from googletrans import Translator
import xml.dom.minidom
import emoji
import requests
import xml.etree.ElementTree as ET
import csv
from typing import List, Optional

# Specify logging level
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('hpack').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.INFO)

# Set DryRun mode
dryRun = False
forceRun = False
noAi = False

# Telegram Bot
telegramBot: telebot.TeleBot

# Default feeds
default_urls = [
                'https://www.amsat.org/feed/',
                'https://qrper.com/feed/',
                'https://swling.com/blog/feed/', 
                'https://www.ari.it/?format=feed&type=rss',
                'https://www.cisar.it/index.php?format=feed&type=rss',
                'https://www.blogger.com/feeds/3151423644013078076/posts/default',
                'https://www.pa9x.com/feed/',
                'https://www.ham-yota.com/feed/',
                'https://www.iu2frl.it/feed/',
                'https://www.yota-italia.it/feed/',
                'https://feeds.feedburner.com/OnAllBands',
                'https://www.hamradio.me/feed',
            ]

# Get bot token from ENV
def get_bot_api_from_env() -> str:
    """Return the bot token from environment variables"""
    # Read API Token from environment variables
    if dryRun:
        return ""
    env_token: str = os.environ.get('BOT_TOKEN')
    if (not env_token):
        logging.critical("Input token is empty!")
        raise Exception("Invalid BOT_TOKEN")
    if (len(env_token) < 10):
        logging.critical("Input token is too short!")
        raise Exception("Invalid BOT_TOKEN")
    if (":" not in env_token):
        logging.critical("Invalid input token format")
        raise Exception("Invalid BOT_TOKEN")
    # Return token
    return str(env_token)

# Get target chat from ENV
def get_target_chat_from_env() -> int:
    """Return the target chat ID from environment variables"""
    if dryRun:
        return ""
    # Read API Token from environment variables
    BOT_TARGET: str = os.environ.get('BOT_TARGET')
    if (not BOT_TARGET):
        logging.critical("Input token is empty!")
        raise Exception("Invalid BOT_TARGET")
    if (len(BOT_TARGET) < 5):
        logging.critical("Input token is too short!")
        raise Exception("Invalid BOT_TARGET")
    # Return token
    return int(BOT_TARGET)

# Get target chat from ENV
def get_admin_chat_from_env() -> int:
    """Return the admin chat ID from environment variables"""
    if dryRun:
        return -1
    # Read API Token from environment variables
    BOT_TARGET: str = os.environ.get('BOT_ADMIN')
    if (not BOT_TARGET):
        logging.warning("Admin is empty! No commands will be accepted")
        return -1
    # Return token
    return int(BOT_TARGET)

# Get maximum news age
def get_max_news_days_from_env() -> int:
    """Return the maximum days a news should be stored from environment variables"""
    if dryRun:
        return 30
    # Read API Token from environment variables
    return int(os.getenv('MAX_NEWS_AGE', default=30))

# Get how many news we should post at each loop
def get_max_news_cnt_from_env() -> int:
    """Return how many news to process from environment variables"""
    return int(os.getenv('NEWS_COUNT', default=1))

# Get post send interval
def get_post_interval_from_env() -> int:
    """Return the publishing interval from environment variables"""
    return int(os.getenv('POST_INTERVAL', default=41))

# Bot initialization
def init_bot():
    """Initialize the Telegram bot class"""
    global telegramBot
    telegramBot = telebot.TeleBot(get_bot_api_from_env())

# Remove HTML code
def remove_html(inputText: str) -> str:
    """Remove html code from the news content"""
    regex_html = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
    return re.sub(regex_html, "", inputText.strip())

# Remove links from text
def remove_links(inputText: str) -> str:
    """Remove links from the news content"""
    # This regex matches URLs with or without http/https, including all subdomains
    regex_link = re.compile(r'(?:https?:\/\/)?(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)')
    return re.sub(regex_link, "", inputText.strip())

# Create news class
class NewsFromFeed(list):
    """Custom class to store news content"""
    title: str = ""
    date: datetime
    author: str = ""
    summary: str = ""
    link: str = ""
    checksum: str = ""

    def __init__(self, inputTitle: str, inputDate: str, inputAuthor: str, inputSummary: str, inputLink: str = "") -> None:
        self.title = inputTitle.strip()
        logging.debug(f"Class title: [{self.title}]")
        self.date = dateutil.parser.parse(inputDate).replace(tzinfo=None)
        logging.debug(f"Class date: [{self.date}]")
        self.author = inputAuthor.strip()
        logging.debug(f"Class author: [{self.author}]")
        if len(inputSummary) > 10:
            # Remove "Read more"
            regex_read_more = re.compile(re.escape("read more"), re.IGNORECASE)
            # Parse summary
            no_read_more = re.sub(regex_read_more, "", inputSummary.strip())
        else:
            no_read_more = inputSummary
        # Remove line feeds
        cut_text = no_read_more.strip().replace('\n', ' ')
        # Remove excessive blank spaces
        while '  ' in cut_text:
            cut_text = cut_text.replace('  ', ' ')
        # Cut input text if too long (Telegram API limitation)
        if len(no_read_more) > 300:
            cut_text = cut_text[:300] + " ..."
        self.summary = cut_text
        logging.debug(f"Class summary: [{self.summary}]")
        clean_url = inputLink.strip().lower()
        self.link = "[" + self.title + "](" + clean_url + ")"
        logging.debug(f"Class url: [{self.link}]")
        # Calculate checksum
        self.checksum = hashlib.md5(clean_url.encode('utf-8')).hexdigest()
        logging.debug(f"Class checksum: [{self.checksum}]")

    def __str__(self):
        return f"[[{self.title}], [{self.date}], [{self.author}], [{self.summary}], [{self.link}], [{self.checksum}]]"

# Extract domain from URL
def extract_domain(url):
    """Extract the domain name from an URL"""
    pattern = r'https?://(?:www\.)?([^/]+)'
    result = re.match(pattern, url)
    if result:
        return result.group(1)
    return "anonymous"

# Get the content of the RSS feed
def fetch_feed(url: str) -> Optional[list]:
    """Fetches the feed content from the URL."""
    try:
        logging.debug(f"Downloading RSS feed from [{url}]")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        logging.debug(f"Retrieved {len(response.content)} bytes from [{url}]")
        return feedparser.parse(response.content)["entries"]
    except requests.RequestException as e:
        logging.error(f"Cannot download feed from [{url}]. Error message: {str(e)}")
    except Exception as e:
        logging.error(f"Cannot parse feed from [{url}]. Error message: {str(e)}")
    return None

# Extract property from the feed
def extract_feed_content(entry, content_key: str) -> Optional[str]:
    """Extracts and cleans content from an RSS entry."""
    logging.debug(f"Searching for [{content_key}]")
    content = entry.get(content_key)
    logging.debug(f"Content: [{str(content)[:20]}...]")
    if content:
        cleaned_content = remove_html(str(content))
        cleaned_content = remove_links(cleaned_content)
        if len(cleaned_content) > 10:
            logging.debug(f"Found value with length: [{len(cleaned_content)}]")
            return cleaned_content
        else:
            logging.warning(f"Skipping [{entry['link']}], content too short.")
    else:
        logging.debug(f"Cannot find [{content_key}] in entry for [{entry['link']}]")
    return None

# Pack the properties to a custom class
def create_article(entry, content_key: str, author_key: str, date_key: str) -> Optional[NewsFromFeed]:
    """Creates a NewsFromFeed object from an entry."""
    try:
        logging.debug(f"Attempting to create article from [{entry['link']}] with content_key [{content_key}, {author_key}, {date_key}]")
        feed_content = extract_feed_content(entry, content_key)
        if feed_content:
            logging.debug(f"Feed content length: [{len(str(feed_content))}]")
            # Try to get author from the feed, if empty return the domain name
            author = entry.get(author_key) or extract_domain(entry["link"])
            logging.debug(f"Getting author with [{author_key}] returned: [{author}]")
            # Try to get the title from the feed
            title = entry["title"]
            if len(title) > 2:
                logging.debug(f"Title returned: [{title}]")
            else:
                title = "No title"
                logging.warning(f"Feed had no title, creating default one")
            # Try to get the link
            link = entry["link"]
            logging.debug(f"Link returned: [{link}]")
            # Try to get date from specified date_key, with fallbacks for common date fields
            date = entry.get(date_key) or entry.get("published") or entry.get("updated")
            logging.debug(f"Getting date with [{date_key}] returned: [{date}]")
            # Build the news class and return it
            if date:
                parsed_feed = NewsFromFeed(title, date, author, feed_content, link)
                logging.debug(f"Feed was properly built, feed content: [{parsed_feed}]")
                return parsed_feed
            else:
                logging.warning(f"Cannot get a valid date using [{date_key}], tried fallbacks 'published' and 'updated'.")
        else:
            logging.warning(f"No valid content for [{entry['link']}]. Skipping entry.")
    except KeyError as e:
        logging.info(f"Missing expected field in [{entry['link']}]. Details: {str(e)}")
    except Exception as e:
        logging.warning(f"Cannot process entry for [{entry['link']}]. Error: {str(e)}")
    return None

# Main parsing function
def parse_news(urls_list: List[str]) -> List[NewsFromFeed]:
    """Parses RSS feeds from a list of URLs and returns a list of NewsFromFeed objects."""
    urls_count = len(urls_list)
    logging.info(f"Parsing news from [{urls_count}] sources, please wait...")
    fetched_feeds = [feed for url in urls_list if (feed := fetch_feed(url))]
    feeds_counter = 1
    news_list = []
    for feed in fetched_feeds:
        logging.debug(f"Parsing feed [{feeds_counter}/{len(fetched_feeds)}]")
        feeds_counter += 1
        for entry in feed:
            logging.debug(f"Processing entry for [{entry['link']}]")
            # Try each possible format key for content, author, and date; stop after first successful one
            for content_key, author_key, date_key in [
                ("description", "dc:creator", "pubDate"), 
                ("summary", "author", "published"),
                ("content", "author", "published")
            ]:
                logging.debug(f"Parsing feed using: {content_key}, {author_key}, {date_key}")
                article = create_article(entry, content_key, author_key, date_key)
                logging.debug(f"Create article returned: {len(str(article))} bytes")
                if article is not None:
                    logging.debug(f"Successfully created article for [{entry['link']}] with content_key [{content_key}]")
                    news_list.append(article)
                    break
                else:
                    logging.debug(f"Attempt to create article with content_key [{content_key}] failed for [{entry['link']}]")

    logging.info(f"Fetched and processed [{len(news_list)}] news items")
    return sorted(news_list, key=lambda news: news.date, reverse=True)

# Handle translation
def translate_text(input_text: str, dest_lang: str = "it") -> str:
    """Translate text using Google APIs"""
    # Check if skip translations
    if noAi:
        return input_text
    # Start text rework
    logging.debug("Translating: [" + input_text + "]")
    translator = Translator()
    translator_response = None
    try:
        translator_response = translator.translate(input_text, dest=dest_lang)
    except Exception as ret_exc:
        logging.error(str(ret_exc))
        return input_text
    logging.debug(translator_response)
    if translator_response is None:
        logging.error("Unable to translate text")
        return input_text
    elif len(translator_response.text) < 10:
        logging.error("Translation was too short")
        return input_text
    return translator_response.text

# Database preparation
def prepare_db() -> None:
    """Prepare the sqlite store"""
    # Connect to SQLite
    logging.debug("Opening SQLite store")
    sqliteConn = get_sql_connector()
    sqliteCursor = sqliteConn.cursor()
    # Create news table
    try:
        sqliteCursor.execute("CREATE TABLE news(date, checksum)")
        logging.info("News table was generated successfully")
    except:
        logging.debug("News table already exists")
    # Count sent articles
    try:
        data_from_db = sqliteCursor.execute("SELECT checksum FROM news WHERE 1").fetchall()
        logging.info("News table contains [" + str(len(data_from_db)) + "] records")
    except Exception as returned_exception:
        logging.critical("Error while getting count of news records: " + str(returned_exception))
        raise Exception(returned_exception)
    # Create feeds table
    try:
        sqliteCursor.execute("CREATE TABLE feeds(url)")
        logging.info("Feeds table was generated successfully")
    except:
        logging.debug("Feeds table already exists")
    # Get feeds from DB
    data_from_db = sqliteCursor.execute("SELECT url FROM feeds WHERE 1").fetchall()
    if (len(data_from_db) < 1):
        logging.info("News table is empty, adding default")
        try:
            for single_url in default_urls:
                logging.debug("Adding [" + single_url + "]")
                sqliteCursor.execute("INSERT INTO feeds(url) VALUES(?)", [single_url])
            sqliteConn.commit()
            if (len(sqliteCursor.execute("SELECT url FROM feeds WHERE 1").fetchall()) < 1):
                raise Exception("Records were not added!")
            logging.debug("Default records were added")
        except Exception as returned_exception:
            logging.error(returned_exception)
            return
    else:
        logging.info("Feeds table contains [" + str(len(data_from_db)) + "] records")
    # Close DB connection
    sqliteConn.close()

# Get SQL Connector
def get_sql_connector() -> sqlite3.Connection:
    """Connect to sqlite"""
    return sqlite3.connect("store/frlbot.db", timeout=3)

# Delete old SQLite records
def remove_old_news(max_days: int = -1) -> int:
    """Delete all old feeds from the database"""
    if max_days == -1:
        max_days = get_max_news_days_from_env()
    try:
        # Get SQL cursor
        sqlCon = get_sql_connector()
        oldNews = sqlCon.cursor().execute("SELECT date FROM news WHERE date <= date('now', '-" + str(max_days) + " day')").fetchall()
        logging.info("Removing [" + str(len(oldNews)) + "] old news from DB")
        sqlCon.cursor().execute("DELETE FROM news WHERE date <= date('now', '-" + str(max_days) + " day')")
        sqlCon.commit()
        sqlCon.close()
        return len(oldNews)
    except Exception as returned_exception:
        logging.error("Cannot delete older news. " + str(returned_exception))
        return -1

# Main code
def main():
    """Main robot code"""
    logging.info("Starting bot")
    # Generate bot object
    global telegramBot
    # Track how many news we sent
    news_cnt: int = 0
    max_news = get_max_news_cnt_from_env()
    # Get SQL cursor
    sql_connector = get_sql_connector()
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
                    if not dryRun:
                        telegramBot.send_message(get_target_chat_from_env(), telegram_payload, parse_mode="MARKDOWN")
                    else:
                        logging.info(telegram_payload)
                    if not dryRun:
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
            if not dryRun:
                telegramBot.send_message(get_admin_chat_from_env(), "Too many errors, skipping this execution. Last error: `" + exception_message + "`")
            break
        # Stop execution after sending x elements
        if news_cnt >= max_news:
            break
    logging.debug("No more articles to process, waiting for next execution")
    # Close DB connection
    sql_connector.close()

# Check if force send
def check_arguments(argv) -> list[bool, bool, bool]:
    """Check CLI arguments"""
    try:
        opts, args = getopt.getopt(argv,"fdn",["force", "dry", "notr"])
        dry_run = False
        force_run = False
        no_translate = False
        for opt, arg in opts:
            if opt in ("-d", "--dry"):
                dry_run = True
            if opt in ("-f", "--force"):
                force_run = True
            if opt in ("-n", "--notr"):
                no_translate = True
        logging.info("DryRun: " + str(dry_run) + " - ForceRun: " + str(force_run) + " - NoTranslate: " + str(no_translate))
        return dry_run, force_run, no_translate
    except:
        return None

# Check if valid XML
def valid_xml(inputUrl: str) -> bool:
    """Check if XML has valid syntax"""
    try:
        getRes = requests.get(inputUrl)
        xml.dom.minidom.parseString(getRes.content)
        return True
    except:
        return False

# Cleanup old news
schedule.every().day.at("01:00").do(remove_old_news, )
# Execute bot news
schedule.every(get_post_interval_from_env()).minutes.do(main, )

# Takes care of scheduled operations (like database cleanup)
def scheduler_loop():
    """Thread to handle the scheduler"""
    logging.info("Starting scheduler loop")
    while True:
        schedule.run_pending()
        time.sleep(5)

# Check inputs from Telegram APIs
def telegram_loop():
    """Thread to handle Telegram commands"""
    logging.info("Starting telegram loop")
    telegramBot.infinity_polling()

# Download a file from an URL
def file_download(url):
    """Read the content of any URL and return the text"""
    response = requests.get(url)
    response.raise_for_status()  # Check if the request was successful
    return response.text

# Import all feeds from OPML file
def opml_import_xmlfeeds(opml_content) -> int:
    """Loop in the OPML file and add each valid feed"""
    root = ET.fromstring(opml_content)
    imported_feeds = 0
    for outline in root.findall(".//outline"):
        xmlFeed = outline.get("xmlUrl")  # Use "xmlUrl" to find xmlFeed
        if xmlFeed:
            if add_feed_if_not_duplicate(xmlFeed):
                imported_feeds += 1
    return imported_feeds

# Add feed to database if not duplicated
def add_feed_if_not_duplicate(feed_url) -> bool:
    """Adds the RSS feed only if valid"""
    sqlCon = get_sql_connector()
    if sqlCon.execute("SELECT * FROM feeds WHERE url=?", [feed_url]).fetchone() is not None:
        logging.warning("Duplicate URL [" + feed_url + "]")
        return False
    else:
        try:
            logging.info("Adding [" + feed_url + "] to DB")
            if valid_xml(feed_url):
                sqlCon.execute("INSERT INTO feeds(url) VALUES(?)", [feed_url])
                logging.debug("Added [" + feed_url + "] to DB")
            else:
                logging.warning("RSS feed [" + feed_url + "] cannot be validated")
                return False
        except Exception as retExc:
            logging.warning(retExc)
            return False
    # Commit changes to DB
    sqlCon.commit()
    sqlCon.close()
    return True

# Main method invocation
if __name__ == "__main__":
    logging.info("Starting frlbot at " + str(datetime.now()))
    # Check if store folder exists
    if not os.path.exists("store"):
        logging.info("Creating 'store' folder")
        os.makedirs("store")
    # Check if script was forcefully run
    try:
        dryRun, forceRun, noAi = check_arguments(sys.argv[1:])
    except:
        logging.critical("Invalid command line arguments have been set")
        exit()
    # Initialize Bot
    if not dryRun:
        init_bot()
        # Handle LIST command
        @telegramBot.message_handler(content_types=["text"], commands=['urllist'])
        def HandleUrlListMessage(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                logging.debug("URL list requested from [" + str(inputMessage.from_user.id) + "]")
                global telegramBot
                sqlCon = get_sql_connector()
                feedsFromDb = [(x[0], x[1]) for x in sqlCon.cursor().execute("SELECT rowid, url FROM feeds WHERE 1").fetchall()]
                sqlCon.close()
                if len(feedsFromDb) < 1:
                    telegramBot.reply_to(inputMessage, "No URLs in the url table")
                else:
                    textMessage: str = ""
                    for singleElement in feedsFromDb:
                        # Check if message is longer than max length
                        if len(textMessage) + len(singleElement[1]) + 10 >= 4096:
                            telegramBot.send_message(inputMessage.from_user.id, textMessage)
                            textMessage = ""
                        textMessage += str(singleElement[0]) + ": " + singleElement[1] + "\n"
                    telegramBot.send_message(inputMessage.from_user.id, textMessage)
            else:
                logging.debug("Ignoring [" + inputMessage.text + "] message from [" + str(inputMessage.from_user.id) + "]")
        # Add new feed to the store   
        @telegramBot.message_handler(content_types=["text"], commands=['addfeed'])
        def HandleAddMessage(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                global telegramBot
                sqlCon = get_sql_connector()
                splitText = inputMessage.text.split(" ")
                if (len(splitText) == 2):
                    # Check if URL is valid
                    if "http" not in splitText[1]:
                        logging.warning("Invalid URL [" + splitText[1] + "]")
                        telegramBot.reply_to(inputMessage, "Invalid URL format")
                        return
                    logging.debug("Feed add requested from [" + str(inputMessage.from_user.id) + "]")
                    # Check if feed already exists
                    if add_feed_if_not_duplicate(splitText[1]):
                        telegramBot.reply_to(inputMessage, "Added successfully!")
                    else:
                        telegramBot.reply_to(inputMessage, "RSS feed cannot be validated (invalid syntax, unreachable or duplicated)")
                else:
                    logging.warning("Invalid AddFeed arguments [" + inputMessage.text + "]")
                    telegramBot.reply_to(inputMessage, "Expecting only one argument")
            else:
                logging.debug("Ignoring [" + inputMessage.text + "] message from [" + str(inputMessage.from_user.id) + "]")
            # Close DB connection
            sqlCon.close()
        # Remove feed from the stores
        @telegramBot.message_handler(content_types=["text"], commands=['rmfeed'])
        def HandleRemoveMessage(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                global telegramBot
                sqlCon = get_sql_connector()
                splitText = inputMessage.text.split(" ")
                if (len(splitText) == 2):
                    if (splitText[1].isnumeric()):
                        logging.debug("Feed deletion requested from [" + str(inputMessage.from_user.id) + "]")
                        try:
                            sqlCon.execute("DELETE FROM feeds WHERE rowid=?", [splitText[1]])
                            sqlCon.commit()
                            sqlCon.close()
                            telegramBot.reply_to(inputMessage, "Element was removed successfully!")
                        except Exception as retExc:
                            telegramBot.reply_to(inputMessage, retExc)
                    else:
                        telegramBot.reply_to(inputMessage, "[" + splitText[1] +"] is not a valid numeric index")
                else:
                    telegramBot.reply_to(inputMessage, "Expecting only one argument")
            else:
                logging.debug("Ignoring [" + inputMessage.text + "] message from [" + str(inputMessage.from_user.id) + "]")
        # Force bot execution
        @telegramBot.message_handler(content_types=["text"], commands=['force'])
        def HandleForceMessage(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                logging.debug("Manual bot execution requested from [" + str(inputMessage.from_user.id) + "]")
                global telegramBot
                telegramBot.reply_to(inputMessage, "Forcing bot execution")
                main()
            else:
                logging.debug("Ignoring [" + inputMessage.text + "] message from [" + str(inputMessage.from_user.id) + "]")
        # Remove old news
        @telegramBot.message_handler(content_types=["text"], commands=['rmoldnews'])
        def HandleOldNewsDelete(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                logging.debug("Manual news deletion requested from [" + str(inputMessage.from_user.id) + "]")
                global telegramBot
                splitMessage = inputMessage.text.split(" ")
                if len(splitMessage) != 2:
                    telegramBot.reply_to(inputMessage, "Expecting only one argument")
                elif splitMessage[1].isdigit():
                    deletedNews = remove_old_news(int(splitMessage[1]))
                    if deletedNews >= 0:
                        telegramBot.reply_to(inputMessage, "Deleting [" + str(deletedNews) + "] news older than [" + str(splitMessage[1]) + "] days")
                    else:
                        telegramBot.reply_to(inputMessage, "Cannot delete older news, check log for error details")
                else:
                    telegramBot.reply_to(inputMessage,"Invalid number of days to delete")
            else:
                logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")
        # Add from CSV list
        @telegramBot.message_handler(content_types=["text"], commands=['addcsv'])
        def HandleAddCsvList(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                logging.debug("Adding news from CSV list")
                global telegramBot
                
                splitMessage = inputMessage.text.split("/addcsv")
                # Invalid syntax
                if len(splitMessage) <= 1:
                    telegramBot.reply_to(inputMessage, "Missing CSV list")
                    return
                splitCsv = splitMessage[1].split(",")
                # Not enough elements
                if len(splitCsv) <= 1:
                    telegramBot.reply_to(inputMessage, "Expecting more than 1 value in CSV format")
                    return
                telegramBot.reply_to(inputMessage, "Processing, please be patient...")
                newFeedsCnt = 0
                for singleUrl in splitCsv:
                    # Clean input string
                    singleUrl = singleUrl.strip()
                    # Add feed if not existing
                    if (add_feed_if_not_duplicate(singleUrl)):
                        newFeedsCnt += 1
                # Send reply
                telegramBot.reply_to(inputMessage, "[" + str(newFeedsCnt) + "] out of [" + str(len(splitCsv)) + "] feeds were added to DB")
            else:
                logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")
        # Perform DB cleanup (duplicate and invalid)
        @telegramBot.message_handler(content_types=["text"], commands=['dbcleanup'])
        def HandleDbCleanup(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                logging.debug("Peforming news cleanup")
                global telegramBot
                telegramBot.reply_to(inputMessage, "Performing cleanup, please be patient...")
                sqlCon = get_sql_connector()
                feedsFromDb = [(x[0], x[1]) for x in sqlCon.cursor().execute("SELECT rowid, url FROM feeds WHERE 1").fetchall()]
                duplicatesCnt = 0
                invalidsCnt = 0
                for singleElement in feedsFromDb:
                    cleanUrl = singleElement[1].split("://")[1].replace("www.", "")
                    logging.debug("Checking for duplicate [" + cleanUrl + "]")
                    # Query to check for duplicate URLs with a different rowid
                    query = "SELECT rowid FROM feeds WHERE url LIKE ? AND rowid != ?"
                    # Execute the query
                    duplicates = sqlCon.cursor().execute(query, ("%" + cleanUrl + "%", singleElement[0])).fetchall()
                    if duplicates:
                        # Remove duplicate
                        logging.info("Removing duplicate [" + singleElement[1] + "] from DB")
                        sqlCon.execute("DELETE FROM feeds WHERE rowid=?", [singleElement[0]])
                        sqlCon.commit()
                        duplicatesCnt += 1
                    else:
                        # Check if feed is valid
                        if not valid_xml(singleElement[1]):
                            # Remove duplicate
                            logging.info("Removing invalid [" + singleElement[1] + "] from DB")
                            sqlCon.execute("DELETE FROM feeds WHERE rowid=?", [singleElement[0]])
                            sqlCon.commit()
                            invalidsCnt += 1
                # Close DB connection
                sqlCon.close()
                # Return output
                telegramBot.reply_to(inputMessage, "Removed [" + str(invalidsCnt) + "] invalid and [" + str(duplicatesCnt) + "] duplicated RSS feeds")
            else:
                logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")
        # Perform DB backup
        @telegramBot.message_handler(content_types=["text"], commands=['sqlitebackup'])
        def HandleSqliteBackup(inputMessage: telebot.types.Message):
            if inputMessage.from_user.id == get_admin_chat_from_env():
                logging.debug("Manual DB backup requested from [" + str(inputMessage.from_user.id) + "]")
                global telegramBot
                try:
                    dbFile = open("store/frlbot.db", "rb")
                    telegramBot.send_document(chat_id=inputMessage.chat.id,
                                            document=dbFile,
                                            reply_to_message_id=inputMessage.id,
                                            caption="SQLite backup at " + str(datetime.now()))
                except Exception as retExc:
                    telegramBot.reply_to(inputMessage, "Error: " + str(retExc))
            else:
                logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")
        # Parse OPML file
        @telegramBot.message_handler(content_types=["text"], commands=['importopml'])
        def HandleImportOPML(inputMessage: telebot.types.Message):
            global telegramBot
            if inputMessage.from_user.id == get_admin_chat_from_env():
                logging.debug("OPML file import requested from [" + str(inputMessage.from_user.id) + "]")
                splitText = inputMessage.text.split(" ")
                if len(splitText) != 2:
                    telegramBot.reply_to(inputMessage, f"Command length is invalid, found {len(splitText)} arguments")
                    logging.warning(f"Invalid OPML import command received: {inputMessage}")
                    return
                else:
                    telegramBot.reply_to(inputMessage, f"Starting OPML file import, please wait")
                    logging.info(f"Starting OPML import of [{splitText[1]}]")
                # Parse OPML file
                try:
                    opml_content = file_download(splitText[1])
                    imported_feeds = opml_import_xmlfeeds(opml_content)
                    telegramBot.reply_to(inputMessage, f"Imported {imported_feeds} feeds")
                except Exception as retExc:
                    telegramBot.reply_to(inputMessage, "Error: " + str(retExc))
            else:
                logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")
    # Prepare DB object
    prepare_db()
    if forceRun:
        logging.info("Starting forced execution")
        main()
        sys.exit(0)
    # Start async execution
    logging.info("Starting main loop")
    if not dryRun:
        telegramThread = threading.Thread(target=telegram_loop, name="TelegramLoop")
        telegramThread.start()
        scheduler_loop()
    else:
        main()