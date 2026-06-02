import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

# Initialize the Supabase client only if credentials are provided
# In MVP/local mode, this might fail if not configured, which is expected
supabase: Client | None = None
if url and key:
    supabase = create_client(url, key)
else:
    print("WARNING: Supabase URL or Key not found in environment variables. Database operations will fail.")
