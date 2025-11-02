from ldap3 import Server, Connection, ALL, Tls
from django.conf import settings
import ssl

def get_members_for_group(group_dn_filter):
    """
    Minimal function to search LDAP groups. group_dn_filter expected to be an LDAP filter expression.
    In practice, you will search by memberOf values as spec'd.
    """
    server = Server(settings.LDAP_IDP_HOSTNAME, get_info=ALL, use_ssl=True)
    conn = Connection(server, user=settings.LDAP_BIND_USER, password=settings.LDAP_BIND_PASS, auto_bind=True)
    # adjust base and search filter for your LDAP
    base_dn = 'ou=people,dc=int,dc=pg,dc=com'
    conn.search(search_base=base_dn, search_filter=group_dn_filter, attributes=['cn', 'mail', 'userPrincipalName'])
    result = []
    for entry in conn.entries:
        # prefer userPrincipalName or mail
        upn = entry.userPrincipalName.value if 'userPrincipalName' in entry else None
        mail = entry.mail.value if 'mail' in entry else None
        result.append(upn or mail or entry.cn.value)
    conn.unbind()
    return result

def get_site_members(site):
    prefix = settings.PERMISSION_PREFIX
    suffix = settings.PERMISSION_SUFFIX_SITE
    # Example memberOf match: ANTG-SITE-<site>
    filt = f"(memberOf={prefix}-{suffix}-{site})"
    return get_members_for_group(filt)

def get_region_members(region):
    prefix = settings.PERMISSION_PREFIX
    suffix = settings.PERMISSION_SUFFIX_REGION
    filt = f"(memberOf={prefix}-{suffix}-{region})"
    return get_members_for_group(filt)
