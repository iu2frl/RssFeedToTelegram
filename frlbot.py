"""Entry point: wires modules together, parses CLI flags and starts the loops."""

import getopt
import logging
import os
import sys
import threading
import time
from datetime import datetime

import schedule

from helpers import bot
from helpers import config
from helpers import database
from helpers import handlers
from helpers.core import main

# Specify logging level
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('hpack').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.INFO)


# Check if force send
def check_arguments(argv) -> list[bool, bool, bool]:
    """Check CLI arguments"""
    try:
        opts, args = getopt.getopt(argv, "fdn", ["force", "dry", "notr"])
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


# Configure the scheduled jobs
def setup_schedule() -> None:
    """Register the recurring scheduled jobs"""
    # Cleanup old news
    schedule.every().day.at("01:00").do(database.remove_old_news, )
    # Execute bot news
    schedule.every(config.get_post_interval_from_env()).minutes.do(main, )


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
    bot.telegram_bot.infinity_polling()


# Main method invocation
if __name__ == "__main__":
    logging.info("Starting frlbot at " + str(datetime.now()))
    # Check if store folder exists
    if not os.path.exists("store"):
        logging.info("Creating 'store' folder")
        os.makedirs("store")
    # Check if script was forcefully run
    try:
        config.dry_run, config.force_run, config.no_ai = check_arguments(sys.argv[1:])
    except:
        logging.critical("Invalid command line arguments have been set")
        exit()
    # Initialize Bot
    if not config.dry_run:
        bot.init_bot()
        handlers.register_handlers()
    # Prepare DB object
    database.prepare_db()
    if config.force_run:
        logging.info("Starting forced execution")
        main()
        sys.exit(0)
    # Start async execution
    logging.info("Starting main loop")
    if not config.dry_run:
        setup_schedule()
        telegramThread = threading.Thread(target=telegram_loop, name="TelegramLoop")
        telegramThread.start()
        scheduler_loop()
    else:
        main()
