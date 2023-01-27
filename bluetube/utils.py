import re


def deemojify(text: str) -> str:
    """Replace all emojis in the given text with □.

    Args:
        text (str): any text

    Returns:
        str: the text without emoji
    """
    regrex_pattern =\
        re.compile(pattern="["
                   u"\U0001F600-\U0001F64F"  # emoticons
                   u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                   u"\U0001F680-\U0001F6FF"  # transport & map symbols
                   u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                   "]+", flags=re.UNICODE)
    return regrex_pattern.sub(r'□', text)
