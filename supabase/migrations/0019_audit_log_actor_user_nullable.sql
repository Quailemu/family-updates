-- 0019_audit_log_actor_user_nullable.sql
-- Permanent fix: allow actor_user_id to be set null when auth user is deleted.

alter table public.audit_log
  alter column actor_user_id drop not null;

