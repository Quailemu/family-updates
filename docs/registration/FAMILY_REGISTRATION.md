# Voice Message – Family Registration & Activation Model
## Invite-Based Self-Activation (Final Decision)

## Contents
1. Philosophy
2. Core model
3. Registration flow
4. Ongoing access & revocation
5. Why no open self-registration
6. Security boundaries
7. Regulatory position

## 1) Philosophy
Family access must be simple, low-admin for care homes, clear in consent boundaries, easy to revoke, and non-technical/calm. We do not use open public self-registration. All family access is anchored by the care home.

## 2) Core Model
Care Home Initiates; Family Self-Activates.
The care home controls who is invited. The family activates themselves via a secure link. This balances control, simplicity, adoption, and legal clarity.

## 3) Registration Flow

### Step 1 – Care Home Invites (Office)
In Care Home Office, for a resident, the care home enters:
- Family member name
- Email address
Then selects: “Send Invite”.

The system generates:
- A secure activation link (single-use)
- Time-limited (e.g., 7 days)

Store:
- invited_by (office user id)
- invited_at
- care_home_id
- resident_id
- invite_contact (masked)
- invite_expires_at
- invite_token_id

### Step 2 – Family Receives Link
Family receives an email with the secure activation/login link. They click the link. No password is required.

### Step 3 – Family Activates
On first access, family:
- Confirms their name (editable)
- Accepts Terms & Privacy Notice
Account becomes active.

Store:
- accepted_at
- accepted_ip (optional)
- accepted_user_agent (optional)

No password creation required.

Authentication thereafter should be lightweight (e.g., remembered session + magic link as fallback).

## 4) Ongoing Access & Revocation
Care Home retains full control. In Office they can:
- Disable a family member instantly (revocation)
- Resend activation link
- Update contact details
- View who is linked to which resident

Revoking access:
- Immediately invalidates sessions
- Sets revoked_at timestamp
- Logs audit event: family_access_revoked

## 5) Why We Do Not Use Open Self-Registration
We do NOT allow families to:
- Register without care home initiation
- Search for residents
- Request access independently

This avoids wrong-resident linking, identity confusion, approval queues, and admin burden. All access originates from the care home.

## 6) Security Boundaries
Family accounts are:
- Linked to a specific resident
- Not globally searchable
- Revocable at any time
- Based on verified contact method (email link)

Family capabilities are limited to product design:
- Send one outbound message
- Receive one inbound message
- No bulk export or archive browsing

## 7) Regulatory Position
This model provides:
- Clear care-home control
- Verifiable activation event
- Explicit acceptance of terms
- Revocation capability
- No uncontrolled public registration

Legal boundary statement:
Family registration is a care-home action between the named care home and the named Family Member for a named resident.
familyupdates.care provides technical infrastructure only and does not decide or approve who is authorised.
Care homes should keep a local registration record including care home name, Family Member name/email, office staff name, and date.

It is proportionate for low-urgency social communication.

Finalised: 2026-02-22
