import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
env_path = os.path.join(BASE_DIR, '.env')
print(f"Loading .env from: {env_path}")

load_dotenv(env_path)

print(f"SECRET_KEY: {os.environ.get('SECRET_KEY')}")
print(f"DEV_MODE: {os.environ.get('DEV_MODE')}")
