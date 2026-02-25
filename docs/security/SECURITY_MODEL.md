# Voice Message – Security Model
## Dedicated Device + Shared PIN (Final Decision)

## Contents
1. Security philosophy
2. Device model
3. Mobile app access model (shared PIN)
4. Session controls
5. Data exposure controls
6. Rationale
7. Regulatory position

## 1) Security Philosophy
Voice Message is a low-urgency, social communication tool. It is not a clinical record system, medication system, financial system, or emergency communication system. Security must be proportionate: protect devices and data from external misuse without creating friction or administrative burden that would block adoption.

## 2) Device Model (Non-negotiable)
- Devices are dedicated and provided for Voice Message use only.
- No personal phones are used.
- Each device has an OS-level device PIN and auto-lock (2–5 minutes).
- Devices remain on-site at the care home.
- If a device is lost, it can be remotely disabled in Office and sessions revoked.

## 3) Mobile App Access Model (Final Decision)
Shared Care-Home PIN:
- Each care home has one shared 4-digit numeric PIN for the Mobile device.
- PIN is stored as a secure hash (never plaintext).
- PIN is changeable in Office if required.
We deliberately do NOT use individual carer logins, biometrics, shift words, SMS codes, or MFA for the Mobile app.

## 4) Session Controls
- Inactivity timeout: 15–20 minutes (configurable).
- After timeout, PIN is required again.
- Optional absolute expiry (e.g., 12 hours) to prevent sessions persisting overnight.

## 5) Data Exposure Controls (Primary Security Layer)
Security does not rely on PIN complexity. The primary protections are:
- No bulk download capability
- No data export
- No full historical archive browsing beyond operational need
- No permanent audio file storage on device (streaming or short-lived cache only)
- Remote device disable

## 6) Rationale for Shared PIN
We chose a shared PIN because:
- This is low-urgency social messaging.
- Individual attribution would add friction and reduce adoption.
- Care environments need low-barrier tools.
- Misconduct is primarily a training/culture issue; authentication does not prevent bad behaviour.

## 7) Regulatory Position
If questioned, we can demonstrate: controlled hardware, access boundary (PIN), automatic session expiry, remote device control, and limited scope of data (non-urgent social messages).

Finalised: 2026-02-22
