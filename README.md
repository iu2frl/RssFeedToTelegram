# RSS Feed to Telegram

This bot reads articles from a list of RSS feeds, translate them to a custom language and sends the output to a Telegram chat (can be any chat, group or channel)

## Live example

See a live example of this code at [IU2FRL Blog channel](https://t.me/iu2frl_news) on Telegram

## Configuration

Working variables are set via environments, these are the used ones:

- `BOT_TOKEN`: contains the Telegram API Token
- `BOT_TARGET`: contains the ID of the Telegram chat were messages should be sent (bot must be admin in case of a channel)
- `BOT_ADMIN`: contains the ID of the bot administrator, the only one which is allowed to send configuration messages (can be a group)
- `MAX_NEWS_AGE`: contains the maximum age in days for an article to be valid
- `NEWS_COUNT`: how many news should be sent per each interval
- `POST_INTERVAL`: how many minutes between publications

## Admin commands

- `/urllist`: returns the list of RSS feeds
- `/addfeed [url]`: adds a new URL to the RSS feeds list
- `/rmfeed [id]`: removes the specified ID from the RSS list
- `/force`: forces a bot execution
- `/rmoldnews`: removes old news from the DB (older than `MAX_NEWS_AGE` days - generally not needed, this is done automatically)
- `/addcsv [url],[url],[...]`: adds a list of RSS feeds separated by commas
- `/dbcleanup`: check if any of the RSS feeds are invalid or duplicated and deletes them from DB
- `/sqlitebackup`: makes a backup of the SQLite database and sends it to the chat
- `/importopml [opml file url]`: to import a list of feeds from an OPML file (example: `https://git.dk1mi.radio/mclemens/Ham-Radio-RSS-Feeds/raw/branch/main/hamradio.opml`)

## Functioning

Every `POST_INTERVAL` minutes, the bot fetches a list of feeds (that is stored in a SQLite file), checks if they are younger than `MAX_NEWS_AGE` days and sends it to the `BOT_TARGET`. Once the message is sent, the checksum for the article URL is calculated and stored in the DB (this is needed to avoid duplicate messages).

Administrator can add, remove, view feeds via custom commands. Database backup is also possible

### Running on Docker

You can use this docker-compose file to run it on your server:

```yaml
services:
  telegram-rss:
    container_name: telegram-rss # Can be any name
    image: iu2frl/telegram-rss:latest # Updated at every release
    environment:
      - "BOT_TOKEN=XXXXXXXXXXXXXXXXXXXXX" # API Key of the bot
      - "BOT_ADMIN=XXXXXXXXXXX" # Chat ID of the administrator
      - "BOT_TARGET=XXXXXXXXXXXXX" # Chat ID where to send news
    restart: unless-stopped
    volumes:
      - frlbot:/home/frlbot/store # Path of the sqlite file
    deploy:
      resources:
        limits: # Optional
          cpus: '1'
          memory: 1024M
volumes:
  frlbot:
```
