"""Runtime configuration: feature flags and environment variable helpers."""

import logging
import os

# Runtime flags (mutated at startup from the CLI arguments)
dry_run = False
force_run = False
no_ai = False

# Default feeds used to seed an empty database
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
    if dry_run:
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
    if dry_run:
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


# Get admin chat from ENV
def get_admin_chat_from_env() -> int:
    """Return the admin chat ID from environment variables"""
    if dry_run:
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
    if dry_run:
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
