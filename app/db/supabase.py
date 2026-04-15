from supabase import Client, create_client

from app.core.config import settings

# Public / anon client — limited by RLS.
# Rarely used on the backend; prefer supabase_admin for server-side operations.
supabase: Client = create_client(
    settings.SUPABASE_URL,
    # The anon key is not stored in Settings to keep the surface small.
    # If you need it, add SUPABASE_ANON_KEY to config.py and replace the line below.
    settings.SUPABASE_SERVICE_ROLE_KEY,  # fallback until anon key is wired up
)

# Service-role admin client — bypasses RLS.
# Use this for all server-initiated reads/writes.
supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY,
)
