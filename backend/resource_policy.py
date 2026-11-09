"""Bounded public publisher origins. A permitted origin is not clinical approval."""
from urllib.parse import urlsplit,parse_qs,urlunsplit
MAX_ACTIVE_RESOURCES=1000
SOURCES={
    'www.who.int':'World Health Organization','www.nhs.uk':'NHS','www.nhsinform.scot':'NHS inform',
    'studentlife.uonbi.ac.ke':'University of Nairobi','sumc.strathmore.edu':'Strathmore University Medical Centre',
    'www.daystar.ac.ke':'Daystar University','counselling.usiu.ac.ke':'USIU-Africa',
    'counseling.mku.ac.ke':'Mount Kenya University','www.kindredcollectivetherapy.com':'Kindred Collective',
    'www.facebook.com':'Befrienders Kenya',
}
def source(value):
    try:
        p=urlsplit(value.strip());host=(p.hostname or '').lower()
        if p.scheme!='https' or host not in SOURCES or p.username or p.password or p.port not in (None,443) or p.fragment:raise ValueError()
        if p.query and parse_qs(p.query,keep_blank_values=True)!={'oai_link_source':['model_response_hotline']}:raise ValueError()
        if host=='www.facebook.com' and p.path.rstrip('/').lower()!='/befrienderskenya':raise ValueError()
        publisher='NHS Every Mind Matters' if host=='www.nhs.uk' and p.path.startswith('/every-mind-matters/') else SOURCES[host]
        return urlunsplit(('https',host,p.path or '/',p.query,'')),publisher
    except (ValueError,TypeError):raise ValueError('Use a listed public HTTPS publisher link without credentials, tracking parameters or fragments. Facebook is limited to the Befrienders Kenya page.') from None
