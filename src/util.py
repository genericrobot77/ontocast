import hashlib


def get_document_hash(text: str) -> str:
    """Generate a hash from the input text."""
    return hashlib.md5(text.encode()).hexdigest()[:8]
