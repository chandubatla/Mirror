from dotenv import load_dotenv
import os

# ✅ Full path to the .env file (for example, one directory above current script)
load_dotenv(dotenv_path="D:/tax/config.env")

# or relative path
load_dotenv(dotenv_path="../.env")   # go one directory up

# then access values
API_KEY = os.getenv("API_KEY")
print(API_KEY)
