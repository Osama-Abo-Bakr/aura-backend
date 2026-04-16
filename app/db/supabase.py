from supabase import Client, create_client

from app.core.config import settings

# Service-role admin client — bypasses RLS.
# The backend always operates with service-role privileges since it verifies
# JWTs itself and scopes all queries by user_id.
supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY,
)
