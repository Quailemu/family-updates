import streamlit as st


st.set_page_config(page_title="Care Hub – Office")
st.title("Care Hub – Office")
st.markdown(
    """
Oversight and administrative control for participating care homes.

## Purpose
Care Hub – Office provides management-level access to the voicemailcare.com platform within your service.

It supports oversight of how the platform is used, while maintaining the care home’s existing governance framework.

## How the Platform Operates
The platform operates on a “one message in, one message out” structure.

Only the most recent message from a family member and the most recent reply from the resident are kept.  
When a new message is sent, the previous message from that sender is replaced.

This structure helps keep communication simple and manageable within care settings.

## Management Functions
Care Hub – Office allows authorised personnel to:
• Manage staff access  
• Enable or disable resident participation  
• Monitor platform usage  
• Maintain oversight of subscription status  

Access is restricted to authorised management users.

## Governance Position
voicemailcare.com provides a communication platform.

The care home remains responsible for:
• Care delivery and safeguarding  
• Regulatory compliance  
• Staff conduct and supervision  
• Decisions regarding resident participation  
• Responding appropriately to family messages  

The platform does not replace the care home’s own policies, safeguarding systems, or complaints procedures.

## Subscription & Agreement
The service is provided under a formal Subscription Agreement.

The current version of the Care Home Subscription Agreement is available here:
**Care Home Subscription Agreement – Version 1.0**
(Download link)

## Support
Platform-related support is available via email.  
Care-related concerns should be addressed through the care home’s own procedures.
"""
)
