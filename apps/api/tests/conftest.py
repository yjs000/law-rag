import os

# Local .env.local may contain real service credentials. Tests must never inherit
# them merely because pytest was started from a developer checkout.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = ""
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["AI_MODE"] = "auto"
os.environ["COLLECTOR_STATE_DIR"] = ".data/nonexistent-api-test-state"
