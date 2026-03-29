import streamlit as st


st.set_page_config(page_title="Privacy Notice")
st.title("Privacy Notice")
st.markdown(
    """
Version 1.0  
Effective Date: [Insert Date]

voicemailcare.com provides a communication platform to care homes under a Subscription Agreement.

We are committed to protecting personal data and complying with applicable UK data protection law.

## 1) Our Role
When a care home subscribes to the service:
• The care home acts as the Data Controller for resident and family data entered into the platform.  
• voicemailcare.com acts as the Data Processor, processing data on behalf of the care home.

## 2) What Data Is Processed
The platform may process:
• Resident name  
• Family member name  
• Email address  
• Voice messages uploaded through the platform  
• Basic usage data (such as login activity)

Only the most recent message from each sender is retained.
The platform is not designed to store long-term communication histories.

## 3) Where Data Is Stored
Data is stored within secure UK-based cloud infrastructure operated by voicemailcare.com.
Logical separation is maintained between participating care homes.

## 4) Purpose of Processing
Data is processed solely to:
• Enable voice message exchange  
• Maintain platform functionality  
• Provide technical support  
• Meet contractual obligations  

The platform is intended for non-urgent social communication.

## 5) Data Retention
The system operates on a “one message in, one message out” structure.
When a new message is sent, the previous message from that sender is replaced.

Upon termination of the Subscription Agreement, personal data will be retained for up to 30 days to allow for administrative processing and potential reactivation.
After this period, personal data will be permanently deleted from active systems.

## 6) Security
We implement reasonable technical and organisational measures to protect data, including:
• Secure hosting  
• Access controls  
• Restricted administrative access  

Care homes remain responsible for managing local device security and staff access.

## 7) Individual Rights
Requests relating to resident or family data should be directed to the relevant care home as Data Controller.

Platform-related data enquiries may be directed to:
hello@voicemailcare.com
"""
)
