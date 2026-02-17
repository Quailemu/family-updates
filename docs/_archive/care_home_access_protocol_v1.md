![logo](../../assets/logo.png)

# Care-home, Carer, and Family Access Protocol - v1 (Final)

## 1. App versions (role separation by design)

We provide three distinct app versions to reduce risk and simplify permissions.

### A. Care Hub – Mobile

Installed on a shared care-home device.  
Device is worn on a lanyard.  
App contains only carer recording and playback tools.

Care Hub – Mobile is a restricted operational view used by carers.
Carers using Care Hub – Mobile cannot access Office/admin functions.

Care Hub – Mobile can:
- record messages with residents
- play the latest family message
- send resident replies

Care Hub – Mobile cannot:
- access family login areas
- show family-only buttons or navigation
- access documents or admin tools

### B. Care Hub – Office

Installed on a desk device for senior staff/admin.  
App contains access management, documents, and oversight tools.

Care Hub – Office provides full access and includes Care Hub – Mobile functionality.

Care Hub – Office can:
- manage access and contacts
- manage documents and contracts
- oversee compliance and device supervision
- perform Care Hub – Mobile tasks when needed for oversight or care delivery
- maintain visibility of messages coming in and going out for oversight

Care Hub – Office cannot:
- access family-only areas

### C. Family app

Installed on personal family devices.  
Contains no care hub tools.  
Families use the Family app only.

This separation is intentional and acts as a data-protection and safeguarding control.

## 2. Devices (care homes)

Shared care-home device (not personal staff devices).

Device is:
- worn on a lanyard
- clearly marked with:
  - app colours
  - care-home name (visible on device / case / lock screen)

Device is treated as shared professional equipment.

Device is returned to the senior staff office at the end of each shift.

This reduces loss, misuse, and ambiguity over ownership.

## 3. Login & shift control (care homes)

### Senior staff (shift authorisation)

At the start of each shift, a senior staff member must unlock Care Hub – Mobile.

This authorises the device for that shift only.

Senior staff may use:
- Face ID / fingerprint (OS-level)
- or password

This login:
- authorises device custody
- does not identify the individual staff member
- does not attach identity to messages

### Carers (during shift)

During an authorised shift:
- carers use a shared PIN or password
- same PIN/password for all carers in that care home

No individual carer accounts are required.

### End of shift

Device is returned to senior staff.  
Next shift requires fresh senior staff authorisation.

This creates a clear handover and custody point without staff surveillance.

## 4. Biometrics (clear scope)

### Allowed

Senior care staff:
- OS-level Face ID / fingerprint to authorise the device at shift start

Families:
- OS-level Face ID / fingerprint to unlock the Family app on personal devices

### Not allowed

- No facial recognition of residents
- No fingerprinting of residents
- No biometric identity checks on residents
- No storage or processing of biometric data by the app

Biometrics are used only to unlock devices owned or formally controlled by the user.

## 5. Resident-supported use (care homes)

Care staff support residents to:
- listen to messages
- record messages
- select family recipients with the resident

Care staff do not:
- use the Family app
- access Care Hub – Office admin functions
- browse across residents freely
- access family app areas

Residents are the voice; staff are the support.

## 6. Message labelling (required)

All messages sent from Care Hub – Mobile must be labelled:

"Recorded with support from the care team."

This avoids impersonation, clarifies staff involvement, and protects carers.

## 7. Data handling & permissions

Care Hub – Mobile must not allow:
- bulk exports
- bulk downloads
- forwarding outside the system

If these are already globally prevented, confirm and enforce for the care-home role.

## 8. Functional goal (keep simple)

Families can hear their loved one’s voice without needing care updates or live contact.  
Carers support residents to record replies when the resident chooses to respond.

## 9. Explicit exclusions (by design)

- No staff surveillance features
- No individual carer tracking
- No resident authentication flows
- No attempt to prevent all staff misconduct (care homes manage staff)
- No biometric gating of residents

## Summary

Safeguarding is achieved through:
- app separation
- shared device custody
- shift-based authorisation
- clear message framing

Not through heavy identity enforcement or surveillance.
