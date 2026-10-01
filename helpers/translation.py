"""Translation helpers built on top of the Google Translate APIs."""

import logging
import asyncio
import httpx
from googletrans import Translator
from httpx_curl_cffi import AsyncCurlTransport

from . import config


async def get_translated_text(input_text: str, dest_lang: str = "it") -> str | None:
    """Translate text asynchronously using Google Translate.

    Args:
        input_text (str): The text to translate.
        dest_lang (str, optional): The target language code. Defaults to "it".

    Returns:
        str | None: The translated text, or None if translation failed.
    """

    # Workaround found at: https://github.com/ssut/py-googletrans/issues/457

    async with Translator(raise_exception=True) as translator:
        
        original_client = translator.client
        
        try:
            # Replace googletrans' HTTPX transport with curl-cffi.
            transport = AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
            )

            translator.client = httpx.AsyncClient(
                transport=transport,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.0.0 Safari/537.36"
                    ),
                },
            )

            # googletrans' TokenAcquirer was created with the original
            # client, so point it at the replacement client as well.
            translator.token_acquirer.client = translator.client

            result = await translator.translate(
                input_text,
                dest=dest_lang,
            )

            # logging.debug("Original: %s", result.origin)
            # logging.debug("Translated:  %s", result.text)
            # logging.debug("src:   %s", result.src)
            # logging.debug("dest:  %s", result.dest)
            # logging.debug("HTTP:  %s", result._response.http_version)
            # logging.debug("status: %s", result._response.status_code)

        except Exception as e:
            logging.error("%s: %s", type(e).__name__, e)

        finally:
            await translator.client.aclose()
            await original_client.aclose()

        return result.text if result else None

# Handle translation
def translate_text(input_text: str, dest_lang: str = "it") -> str:
    """Translate text using Google APIs"""
    # Check if skip translations
    if config.no_ai:
        return input_text

    # Start text rework
    logging.debug("Translating: [%s] to [%s]", input_text, dest_lang)

    translator_text = ""

    loop = asyncio.get_event_loop()
    translator_text = loop.run_until_complete(get_translated_text(input_text, dest_lang))

    logging.debug("Translated text: %s", translator_text)
    if not translator_text:
        logging.error("Unable to translate text")
        return input_text
    elif len(translator_text) < 10:
        logging.error("Translation was too short")
        return input_text
    return translator_text
