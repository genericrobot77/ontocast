import hashlib


def render_text_hash(text: str, digits=12) -> str:
    """
    Generate a hash for the given text.

    Args:
        text: The text to hash
        digits: Number of digits in the hash (default: 12)

    Returns:
        A string hash of the text
    """
    return hashlib.sha256(text.encode()).hexdigest()[:digits]
