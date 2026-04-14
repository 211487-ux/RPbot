import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_PREFIX = "!"

# Google Docs Configuration
GOOGLE_DOCS_TIMEOUT = 20  # seconds

# NPC Configuration
MAX_NPCS_PER_SERVER = 200
MAX_PLAYER_LORE_SIZE = 50000  # characters

# Response Configuration
RESPONSE_DELAY = 0.5  # seconds
MAX_RESPONSE_LENGTH = 2000  # Discord message limit
