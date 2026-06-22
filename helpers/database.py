"""SQLite persistence layer: feeds and sent-news storage."""

import logging
import sqlite3
import xml.etree.ElementTree as ET

from . import config
from .feeds import valid_xml


# Get SQL Connector
def get_sql_connector() -> sqlite3.Connection:
    """Connect to sqlite"""
    return sqlite3.connect("store/frlbot.db", timeout=5)


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
            for single_url in config.default_urls:
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


# Delete old SQLite records
def remove_old_news(max_days: int = -1) -> int:
    """Delete all old feeds from the database"""
    if max_days == -1:
        max_days = config.get_max_news_days_from_env()
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
