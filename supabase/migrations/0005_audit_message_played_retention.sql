-- Add resident-aware playback auditing with safe dedupe and retention support.

alter table public.audit_log
  add column if not exists resident_id uuid references public.residents(id) on delete set null;

create index if not exists idx_audit_log_resident_id
  on public.audit_log (resident_id);

create unique index if not exists uq_audit_message_played_actor_message
  on public.audit_log (action, resident_id, actor_user_id, target_id)
  where action = 'message_played'
    and resident_id is not null
    and target_id is not null;

drop policy if exists "audit_log_delete_care_hub" on public.audit_log;
create policy "audit_log_delete_care_hub"
on public.audit_log
for delete
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = audit_log.care_home_id
      and chu.active = true
  )
);
