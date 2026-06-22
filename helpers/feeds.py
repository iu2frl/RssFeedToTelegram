"""RSS/Atom feed downloading, parsing and validation helpers."""

import logging
import xml.dom.minidom
from typing import List, Optional

import feedparser
import requests

from .models import NewsFromFeed
from .text_utils import extract_domain, remove_html, remove_links


# Get the content of the RSS feed
def fetch_feed(url: str) -> Optional[list]:
    """Fetches the feed content from the URL."""
    try:
        logging.debug(f"Downloading RSS feed from [{url}]")
        response = requests.get(url, timeout=5)
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
        # feedparser sometimes returns complex objects (list/dict) instead of
        # plain strings. `str()` of these objects ends up in the message with
        # Python syntax, which is what the user observed. We need to unpack
        # and select the actual text value (often under 'value' or 'valore').
        def _unwrap(obj):
            # handle lists by unwrapping each element
            if isinstance(obj, list):
                for item in obj:
                    result = _unwrap(item)
                    if result:
                        return result
                return ''
            # handle dicts by looking for common keys or concatenating values
            if isinstance(obj, dict):
                for k in ('value', 'valore', 'text', 'description'):
                    if k in obj and obj[k]:
                        return _unwrap(obj[k])
                # fallback: join child values
                return ' '.join(_unwrap(v) for v in obj.values() if v)
            # fallback: just stringify
            return str(obj)

        raw_text = _unwrap(content)
        cleaned_content = remove_html(raw_text)
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
            try:
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
            except Exception as ex:
                logging.warning(f"Failed to parse article: {ex}")

    logging.info(f"Fetched and processed [{len(news_list)}] news items")
    return sorted(news_list, key=lambda news: news.date, reverse=True)


# Check if valid XML
def valid_xml(inputUrl: str) -> bool:
    """Check if XML has valid syntax"""
    try:
        getRes = requests.get(inputUrl, timeout=5)
        xml.dom.minidom.parseString(getRes.content)
        return True
    except:
        return False


# Download a file from an URL
def file_download(url):
    """Read the content of any URL and return the text"""
    response = requests.get(url, timeout=5)
    response.raise_for_status()  # Check if the request was successful
    return response.text
