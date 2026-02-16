# Supabase migrations

## Apply the migration

1) Open the Supabase SQL editor for your project.
2) Paste the contents of `supabase/migrations/0001_init.sql`.
3) Run the script.

## If a step fails

- Run the file section-by-section in the same order (extensions → tables → constraints/indexes → RLS → storage).
- If a policy already exists, ensure the `drop policy if exists` statements ran before re-creating it.

## Deploy the Edge Function

1) Ensure the Supabase CLI is installed and linked to your project.
2) Set function secrets in Supabase (Project Settings → Functions):
   - `VM_SUPABASE_URL`
   - `VM_SUPABASE_ANON_KEY`
   - `VM_SUPABASE_SERVICE_ROLE_KEY`
3) Deploy the function:
   - `supabase functions deploy get_audio_signed_url`
4) This function disables gateway JWT verification (see `supabase/config.toml`) and validates JWTs inside the function.
