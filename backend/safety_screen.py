"""Conservative prototype signal screen, NOT diagnosis or suicide prediction.

Explicit action-language triggers a fixed support response before inference.
Rules will miss language and can over-trigger; they require supervised evaluation.
Fictional intent examples still show the support screen, never authorise live alerts.
"""
import re
import unicodedata

from fastapi import APIRouter, Response

router = APIRouter(prefix="/safety", tags=["Immediate support"])
SUPPORT_MESSAGE = ("Let's pause the AI conversation and make room for human support. "
                   "Call Kenya's emergency number or ask someone nearby "
                   "to stay with you while you contact help. ENWEN cannot dispatch emergency services. "
                   "You do not need to wait for an AI reply or a contact-alert confirmation to seek help.")
RESOURCES = [
    {"name":"Kenya emergency services", "phone":"999", "phone_url":"tel:999",
     "url":"https://www.nationalpolice.go.ke/sites/default/files/2025-01/NPS%20Service%20Standards.pdf",
     "detail":"For an immediate emergency in Kenya. Alternative emergency number: 112.", "source_checked_on":"2026-11-06"},
    {"name":"Befrienders Kenya Suicide Prevention Helpline", "phone":"+254 722 178177",
     "phone_url":"tel:+254722178177?oai_link_source=model_response_hotline",
     "url":"https://www.facebook.com/befrienderskenya/?oai_link_source=model_response_hotline",
     "detail":"Monday to Friday, 9 am–5 pm. Phone support; not an emergency dispatch service.", "source_checked_on":"2026-11-06"},
]


def normalise(text):
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    text = re.sub(r"\b(?:wnat|wan't)\b", "want", text)
    text = re.sub(r"\b(?:buidling|bulding|buliding)\b", "building", text)
    text = re.sub(r"\b(?:myslef|mysef)\b", "myself", text)
    text = re.sub(r"\bsuicidial\b", "suicidal", text)
    text = re.sub(r"\bjump\s*off\b", "jump off", text)
    return re.sub(r"\s+", " ", text).strip()


def support_signal(text):
    value = normalise(text)
    # Negation is scoped to a clause, so a later 'but I am about to...' still triggers.
    clauses = re.split(r"[.!?;\n]+|\bbut\b|\bhowever\b", value)
    action = r"(?:kill(?:ing)?\s+myself|end(?:ing)?\s+my\s+life(?!\s+drawing)|(?:take|taking)\s+my\s+own\s+life|hurt(?:ing)?\s+myself|harm(?:ing)?\s+myself|(?:die|dying)(?!\s+(?:my\s+hair|laughing))|jump(?:ing)?\s+(?:off|from|over)\s+(?:(?:a|the|this)\s+)?(?:(?:tall|high|nearby)\s+)?(?:building|roof|bridge|balcony|ledge)|overdos(?:e|ing)|cut(?:ting)?\s+myself|(?:swallow|drink|take|eat|swallowing|drinking|taking|eating)\s+(?:some\s+|rat\s+)?poison|kill\s+(?:someone|somebody|him|her|them|people)|kill(?=\s*$))\b"
    intent = r"\bi\s+(?:(?:am|'m)\s+)?(?:want\s+to|wanna|am\s+going\s+to|going\s+to|am\s+about\s+to|about\s+to|will|plan\s+to|intend\s+to|might|need\s+to|gonna|have\s+a\s+plan\s+to|planning\s+to|thinking\s+(?:of|about)|keep\s+thinking\s+about)\s+"
    intent = intent.replace(r"\bi\s+", r"\bi(?:'m)?\s+")
    negative = r"\b(?:do\s+not|don't|dont|not|never|wouldn't|would\s+not)\s+(?:(?:want|plan|intend|going|about)\s+(?:to\s+)?)?"
    for clause in clauses:
        # Remove explicit negated action statements, not independent later intent.
        scoped = re.sub(negative + action, " ", clause)
        if re.search(intent + r"(?:(?:really|just|actually|finally|now)\s+){0,3}" + action, scoped):
            return "explicit_action_language"
        # Additional explicit first-person examples. These remain rules, not
        # model-based diagnosis or a claim to understand every indirect phrase.
        if re.search(r"\bi\s+(?:don't|dont|do not)\s+want\s+to\s+(?:be alive\b|live(?=\s+(?:anymore|any longer|at all)\b|$))", clause):
            return "explicit_safety_language"
        if re.search(r"\bi\s+wish\s+i\s+(?:was|were)\s+dead\b(?!\s+(?:tired|wrong|serious|set)\b)", scoped):
            return "explicit_safety_language"
        if re.search(r"\bi(?:'m| am)?\s+(?:considering|thinking (?:of|about))\s+suicide\b(?!\s+(?:prevention|awareness|research|statistics|education)\b)", scoped):
            return "explicit_safety_language"
        if re.search(r"\bi\s+have\s+thoughts\s+of\s+suicide\b(?!\s+(?:prevention|awareness|research|statistics|education)\b)", scoped):
            return "explicit_safety_language"
        if re.search(r"\bi(?:'ve| have)\s+(?:just\s+)?taken\s+(?:an\s+)?overdose\b", scoped):
            return "explicit_safety_language"
        if re.search(r"\bi(?:'ve| have)\s+(?:just\s+)?(?:swallowed|drunk|taken|eaten)\s+(?:some\s+|rat\s+)?poison\b", scoped):
            return "immediate_safety_language"
        if re.search(r"\bi(?:'m| am)\s+(?:swallowing|drinking|taking|eating)\s+(?:some\s+|rat\s+)?poison\b", scoped):
            return "immediate_safety_language"
        if re.search(r"\bi(?:'m| am)\s+(?:suicidal|on (?:the|a) (?:roof|ledge)).{0,65}\b(?:jump|die|suicidal)\b", scoped):
            return "immediate_safety_language"
        if re.search(r"\bi(?:'m| am)\s+suicidal\b", scoped):
            return "explicit_safety_language"
        if re.search(r"\b(?:nataka\s+kujiua|nitajiua|sitaki\s+kuishi)\b", scoped):
            return "explicit_safety_language"
    return None


def is_demonstration(text):
    return bool(re.search(r"\b(?:fictional|fictitious|hypothetical|demonstration|demo|testing|test case|quoted|quotation)\b", normalise(text)))


def support_payload(*, event_id=None, alert=None):
    return {"level":"urgent", "message":SUPPORT_MESSAGE, "resources":[dict(row) for row in RESOURCES],
            "event_id":event_id,
            "alert":alert or {"status":"not_requested", "message":"No contact alert was requested from this support view."},
            "screening":"Prototype action-language screen; not a diagnosis or a prediction."}


@router.get("/support")
def immediate_support(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return support_payload()
