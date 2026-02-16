![logo](../../assets/logo.png)

# Test accounts (developer reference)

## Purpose

This file lists test accounts used for login flows. Supabase is the source of truth.

## Rules

- No passwords, tokens, or API keys.
- Use fake data only.
- Keep in sync with Supabase.

## Family accounts

| Label | Email | Supabase user ID | Care home ID | Notes |
| --- | --- | --- | --- | --- |
| Family 1 | family1@test.local | b70b70db-4c87-4b43-b809-b35a63322dd0 |  |  |
| Family 2 | family2@test.local | a1aff7d4-31e5-4c21-9bcc-5a6c086d08b3 |  |  |

## Care Hub – Mobile accounts

| Label | Email | Supabase user ID | Care home ID | Notes |
| --- | --- | --- | --- | --- |
| Operator (shared) | operator.pilot@test.local | 45739434-d0e8-43c0-acc5-5f6ab1eb81d0 |  | Shared operator login |

## Care Hub – Office accounts

| Label | Email | Supabase user ID | Care home ID | Notes |
| --- | --- | --- | --- | --- |
| Operator A | operatora@test.local | 0c736b6c-9861-4bfd-9844-7faa2458fe19 |  |  |
| Operator B | operatorb@test.local | 36715a9a-1d3d-4b7a-a608-470e489069cb |  |  |

## Mapping notes

- Family accounts are mapped via `family_contacts`.
- Care Hub accounts are mapped via `care_home_users`.
- Shared operator login may be used for staff accounts.

## Maintenance

- Update after any Supabase test account changes.
