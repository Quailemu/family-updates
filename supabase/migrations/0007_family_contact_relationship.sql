-- 0007_family_contact_relationship.sql
-- Adds an optional relationship label for family contacts (for example:
-- daughter, son, spouse, friend) to improve care-side contact selection clarity.

alter table public.family_contacts
  add column if not exists relationship text;

