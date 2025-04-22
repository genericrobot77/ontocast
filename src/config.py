import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Domain configuration
CURRENT_DOMAIN = os.getenv("CURRENT_DOMAIN", "https://example.com")
CURRENT_NS_IRI = os.getenv("CURRENT_NS_IRI", "https://example.com/current-document#")
