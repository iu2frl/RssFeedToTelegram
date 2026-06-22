"""Translation helpers built on top of the Google Translate APIs."""

import logging

from googletrans import Translator

from . import config


# Handle translation
def translate_text(input_text: str, dest_lang: str = "it") -> str:
    """Translate text using Google APIs"""
    # Check if skip translations
    if config.no_ai:
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
