-- Optional care-home banner content for Mobile/Office header area.
-- Allows each care home to add custom text and optional artwork URL.

alter table public.care_homes
  add column if not exists branding_banner_title text,
  add column if not exists branding_banner_text text,
  add column if not exists branding_banner_artwork_url text;

