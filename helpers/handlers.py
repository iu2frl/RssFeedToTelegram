"""Telegram command handlers (admin-only configuration commands)."""

import logging
from datetime import datetime

import telebot

from . import bot
from . import config
from . import database
from .core import main
from .feeds import file_download, valid_xml


def register_handlers() -> None:
    """Register every Telegram command handler on the shared bot instance"""
    telegramBot = bot.telegram_bot

    # Handle LIST command
    @telegramBot.message_handler(content_types=["text"], commands=['urllist'])
    def HandleUrlListMessage(inputMessage: telebot.types.Message):
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            logging.debug("URL list requested from [" + str(inputMessage.from_user.id) + "]")
            sqlCon = database.get_sql_connector()
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
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            sqlCon = database.get_sql_connector()
            splitText = inputMessage.text.split(" ")
            if (len(splitText) == 2):
                # Check if URL is valid
                if "http" not in splitText[1]:
                    logging.warning("Invalid URL [" + splitText[1] + "]")
                    telegramBot.reply_to(inputMessage, "Invalid URL format")
                    return
                logging.debug("Feed add requested from [" + str(inputMessage.from_user.id) + "]")
                # Check if feed already exists
                if database.add_feed_if_not_duplicate(splitText[1]):
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
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            sqlCon = database.get_sql_connector()
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
                    telegramBot.reply_to(inputMessage, "[" + splitText[1] + "] is not a valid numeric index")
            else:
                telegramBot.reply_to(inputMessage, "Expecting only one argument")
        else:
            logging.debug("Ignoring [" + inputMessage.text + "] message from [" + str(inputMessage.from_user.id) + "]")

    # Force bot execution
    @telegramBot.message_handler(content_types=["text"], commands=['force'])
    def HandleForceMessage(inputMessage: telebot.types.Message):
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            logging.debug("Manual bot execution requested from [" + str(inputMessage.from_user.id) + "]")
            telegramBot.reply_to(inputMessage, "Forcing bot execution")
            main()
        else:
            logging.debug("Ignoring [" + inputMessage.text + "] message from [" + str(inputMessage.from_user.id) + "]")

    # Remove old news
    @telegramBot.message_handler(content_types=["text"], commands=['rmoldnews'])
    def HandleOldNewsDelete(inputMessage: telebot.types.Message):
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            logging.debug("Manual news deletion requested from [" + str(inputMessage.from_user.id) + "]")
            splitMessage = inputMessage.text.split(" ")
            if len(splitMessage) != 2:
                telegramBot.reply_to(inputMessage, "Expecting only one argument")
            elif splitMessage[1].isdigit():
                deletedNews = database.remove_old_news(int(splitMessage[1]))
                if deletedNews >= 0:
                    telegramBot.reply_to(inputMessage, "Deleting [" + str(deletedNews) + "] news older than [" + str(splitMessage[1]) + "] days")
                else:
                    telegramBot.reply_to(inputMessage, "Cannot delete older news, check log for error details")
            else:
                telegramBot.reply_to(inputMessage, "Invalid number of days to delete")
        else:
            logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")

    # Add from CSV list
    @telegramBot.message_handler(content_types=["text"], commands=['addcsv'])
    def HandleAddCsvList(inputMessage: telebot.types.Message):
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            logging.debug("Adding news from CSV list")

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
                if (database.add_feed_if_not_duplicate(singleUrl)):
                    newFeedsCnt += 1
            # Send reply
            telegramBot.reply_to(inputMessage, "[" + str(newFeedsCnt) + "] out of [" + str(len(splitCsv)) + "] feeds were added to DB")
        else:
            logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")

    # Perform DB cleanup (duplicate and invalid)
    @telegramBot.message_handler(content_types=["text"], commands=['dbcleanup'])
    def HandleDbCleanup(inputMessage: telebot.types.Message):
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            logging.debug("Peforming news cleanup")
            telegramBot.reply_to(inputMessage, "Performing cleanup, please be patient...")
            sqlCon = database.get_sql_connector()
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
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
            logging.debug("Manual DB backup requested from [" + str(inputMessage.from_user.id) + "]")
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
        if inputMessage.from_user.id == config.get_admin_chat_from_env():
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
                imported_feeds = database.opml_import_xmlfeeds(opml_content)
                telegramBot.reply_to(inputMessage, f"Imported {imported_feeds} feeds")
            except Exception as retExc:
                telegramBot.reply_to(inputMessage, "Error: " + str(retExc))
        else:
            logging.debug("Ignoring message from [" + str(inputMessage.from_user.id) + "]")
