import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./predictivebio.db")
