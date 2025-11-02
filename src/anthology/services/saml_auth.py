"""
SAML authentication helpers.
Use python3-saml (onelogin) or djangosaml2 in production.
This file contains helper signatures and comments for proper implementation.
"""

from django.conf import settings

def parse_and_validate_saml_response(saml_response_raw):
    """
    Validate signature, timestamps, audience, and return extracted attributes dict:
    {
      'username': 'dev.user',
      'displayName': 'Dev User',
      'memberOf': ['ANTG-ADMIN', 'ANTG-SITE-SITEA', ...],
      ...
    }
    """
    raise NotImplementedError("Implement SAML validation using python3-saml or djangosaml2")
