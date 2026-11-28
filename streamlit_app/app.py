from __future__ import annotations
import os
from datetime import datetime, timezone, timedelta
from urllib import response
import requests
import streamlit as st
import extra_streamlit_components as stx
import jwt
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def _api_base() -> str:
    """Streamlit secrets first (Streamlit Cloud), then the environment variable, then localhost."""
    try:
        configured = st.secrets.get("MEDICYCLE_API_URL")
    except Exception:  # no secrets.toml, e.g. a local run: newer Streamlit raises instead of returning None
        configured = None
    return (configured or os.getenv("MEDICYCLE_API_URL", "http://127.0.0.1:8000")).rstrip("/")


API_BASE = _api_base()
AUTH_COOKIE_NAME = "medicycle_access_token"


def _persist_access_token(cookie_manager, token: str) -> None:
    """Persist the bearer token only until the JWT's own expiry."""
    try:
        claims = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        expires_at = datetime.fromtimestamp(float(claims["exp"]), tz=timezone.utc)
    except (jwt.PyJWTError, KeyError, TypeError, ValueError, OverflowError):
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)

    remaining = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    cookie_manager.set(
        AUTH_COOKIE_NAME, token, key="medicycle_set_auth", path="/",
        expires_at=expires_at, max_age=remaining, secure=True, same_site="strict",
    )

st.set_page_config(page_title='MediCycle', page_icon='♻️', layout='wide', initial_sidebar_state='expanded')

# Visual system: presentation only; API calls and business workflows remain unchanged.
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --mc-ink:#143b35; --mc-muted:#6d8580; --mc-green:#13866f; --mc-line:#dce9e4; --mc-paper:#f6faf8; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:var(--mc-paper); color:var(--mc-ink); }
.block-container { max-width:1380px; padding-top:2.1rem; padding-bottom:3rem; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; color:var(--mc-ink) !important; letter-spacing:-.035em; }
h1 { font-weight:800 !important; } h2,h3 { font-weight:700 !important; }
p, label { color:#526d66; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#eaf5f0 0%,#f4faf7 100%); border-right:1px solid var(--mc-line); }
[data-testid="stSidebar"] > div:first-child { padding-top:1.6rem; }
[data-testid="stMetric"] { background:#fff; border:1px solid var(--mc-line); border-radius:18px; padding:19px 20px; box-shadow:0 5px 18px rgba(20,59,53,.035); }
[data-testid="stMetricLabel"] p { color:var(--mc-muted) !important; font-weight:600; }
[data-testid="stMetricValue"] { color:var(--mc-ink); font-family:'Manrope',sans-serif; font-weight:800; }
.stButton > button, .stFormSubmitButton > button { border-radius:11px; min-height:2.8rem; font-weight:700; border:1px solid #cbded6; transition:all .18s ease; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:var(--mc-green); border-color:var(--mc-green); color:#fff; }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color:var(--mc-green); color:var(--mc-green); transform:translateY(-1px); }
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover { background:#0d705d; color:#fff; }
input, textarea, [data-baseweb="select"] > div { border-radius:10px !important; }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { background:#fff; border-color:#d6e4de; }
[data-testid="stTabs"] button { font-weight:700; }
[data-testid="stDataFrame"] { border:1px solid var(--mc-line); border-radius:14px; overflow:hidden; }
[data-testid="stAlert"] { border-radius:12px; }
.mc-brand { display:flex; align-items:center; gap:13px; margin:0 0 8px; }
.mc-mark { width:52px; height:52px; border-radius:16px; display:grid; place-items:center; color:#fff; font-size:27px; background:linear-gradient(145deg,#35c69a,#08765f); box-shadow:0 9px 22px rgba(19,134,111,.2); }
.mc-wordmark { font-family:'Manrope',sans-serif; font-size:2.1rem; font-weight:800; letter-spacing:-.06em; color:var(--mc-ink); }
.mc-tagline { color:#6c8780; font-size:.98rem; margin:0 0 1.8rem 2px; }
.mc-auth-hero { min-height:480px; height:100%; padding:42px 38px; border-radius:24px; color:white; background:radial-gradient(circle at 82% 18%,rgba(111,232,190,.3),transparent 27%),linear-gradient(145deg,#123e36,#0b7561); display:flex; flex-direction:column; justify-content:space-between; box-shadow:0 18px 42px rgba(15,70,59,.14); }
.mc-auth-hero h2 { color:white !important; font-size:2.1rem; line-height:1.18; margin:.8rem 0 1rem; }
.mc-auth-hero p { color:#d1eee4; line-height:1.7; }
.mc-pill { display:inline-block; padding:7px 12px; border:1px solid rgba(255,255,255,.25); border-radius:30px; color:#d9fff0; font-size:.78rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; width:max-content; }
.mc-feature-list { display:grid; gap:13px; margin-top:28px; }
.mc-feature { display:flex; align-items:center; gap:12px; color:#e6fff5; font-size:.93rem; }
.mc-feature span { display:grid; place-items:center; width:29px; height:29px; border-radius:9px; background:rgba(255,255,255,.14); }
.mc-section-label { color:var(--mc-green); font-size:.75rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; margin-bottom:7px; }
.mc-subtle { color:#718780; font-size:.9rem; }

/* ---- Streamlit workspace polish ---- */
.stApp { background:linear-gradient(180deg,#f4faf7 0%,#f8fbfa 260px,#f7faf9 100%); }
.block-container { padding-left:clamp(1.2rem,4vw,3.2rem); padding-right:clamp(1.2rem,4vw,3.2rem); }
[data-testid="stHeader"] { background:rgba(247,251,249,.82); backdrop-filter:blur(14px); }
[data-testid="stSidebar"] { box-shadow:8px 0 28px rgba(20,59,53,.035); }
[data-testid="stSidebar"] [data-testid="stRadio"] > label { font-size:.72rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; color:#82958f; }
[data-testid="stSidebar"] [role="radiogroup"] { gap:5px; }
[data-testid="stSidebar"] [role="radiogroup"] label { padding:10px 12px; border-radius:11px; transition:background .18s ease,transform .18s ease; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background:rgba(19,134,111,.08); transform:translateX(2px); }
[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] { background:#dcefe7; color:#0b705c; font-weight:700; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:#e0ebe6 !important; border-radius:17px !important; background:rgba(255,255,255,.88); box-shadow:0 7px 24px rgba(20,59,53,.045); }
[data-testid="stMetric"] { min-height:116px; display:flex; flex-direction:column; justify-content:center; transition:transform .2s ease,box-shadow .2s ease; }
[data-testid="stMetric"]:hover { transform:translateY(-2px); box-shadow:0 12px 28px rgba(20,59,53,.075); }
[data-testid="stMetricDelta"] { font-weight:700; }
[data-testid="stTabs"] [role="tablist"] { gap:7px; border-bottom:1px solid #e2ece7; }
[data-testid="stTabs"] button[role="tab"] { border-radius:10px 10px 0 0; padding:10px 15px; color:#718780; }
[data-testid="stTabs"] button[aria-selected="true"] { color:#08765f; border-bottom-color:#13866f; }
[data-testid="stExpander"] { border:1px solid #e0ebe6; border-radius:14px; background:rgba(255,255,255,.76); overflow:hidden; }
.stButton > button, .stFormSubmitButton > button { box-shadow:0 3px 9px rgba(20,59,53,.045); }
.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible { outline:3px solid rgba(19,134,111,.22); outline-offset:2px; }
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus { border-color:#13866f !important; box-shadow:0 0 0 3px rgba(19,134,111,.12) !important; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stDateInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTimeInput"] input { background:#fff; border-color:#dce9e4; border-radius:11px; }
[data-testid="stAlert"] { border:1px solid #e1ebe6; box-shadow:0 3px 12px rgba(20,59,53,.025); }
[data-testid="stDataFrame"] { background:#fff; box-shadow:0 5px 18px rgba(20,59,53,.035); }
hr { border-color:#e2ece7 !important; }
.mc-page-intro { display:flex; align-items:center; justify-content:space-between; gap:16px; margin:0 0 1.15rem; padding:17px 20px; border:1px solid #e0ebe6; border-radius:16px; background:linear-gradient(110deg,#fff 0%,#f0f8f4 100%); box-shadow:0 7px 22px rgba(20,59,53,.035); }
.mc-page-intro small { color:#13866f; font-size:.7rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
.mc-page-intro strong { display:block; margin-top:3px; color:#143b35; font-family:'Manrope',sans-serif; font-size:1.05rem; }
.mc-page-intro span { color:#718780; font-size:.84rem; }
.mc-profile-card { border:1px solid #dce9e4; border-radius:20px; background:linear-gradient(115deg,#fff 0%,#f0f8f4 100%); padding:20px; box-shadow:0 9px 28px rgba(20,59,53,.055); }
@media(max-width:700px) {
 .block-container { padding-top:1.2rem; }
 [data-testid="stMetric"] { min-height:96px; padding:14px; }
 .mc-auth-hero { min-height:280px; }
}
@media(prefers-reduced-motion:reduce) {
 *,*::before,*::after { scroll-behavior:auto !important; animation-duration:.01ms !important; animation-iteration-count:1 !important; transition-duration:.01ms !important; }
}
@media(max-width:900px){ .mc-auth-hero{min-height:300px;padding:28px;} .mc-auth-hero h2{font-size:1.65rem;} .mc-wordmark{font-size:1.7rem;} }

/* ---- Motion polish: restrained, accessible micro-interactions ---- */
@keyframes mc-page-enter {
  from { opacity: 0; transform: translateY(7px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes mc-soft-reveal {
  from { opacity: 0; transform: translateY(9px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes mc-brand-glow {
  0%, 100% { box-shadow: 0 9px 22px rgba(19,134,111,.18); }
  50%      { box-shadow: 0 11px 28px rgba(19,134,111,.28); }
}
.main .block-container { animation: mc-page-enter .42s cubic-bezier(.2,.7,.25,1) both; }
.mc-mark { animation: mc-brand-glow 5s ease-in-out infinite; }
[data-testid="stMetric"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpander"],
[data-testid="stDataFrame"] {
  transition: transform .22s cubic-bezier(.2,.7,.25,1),
              box-shadow .22s ease, border-color .22s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
  transform: translateY(-2px);
  border-color: #c9e2d7 !important;
  box-shadow: 0 12px 30px rgba(20,59,53,.075) !important;
}
[data-testid="stMetric"]:hover {
  transform: translateY(-3px);
  box-shadow: 0 13px 30px rgba(20,59,53,.085);
}
.stButton > button,
.stFormSubmitButton > button,
[data-testid="stDownloadButton"] > button {
  transition: transform .18s ease, box-shadow .18s ease,
              background-color .18s ease, border-color .18s ease;
}
.stButton > button:hover,
.stFormSubmitButton > button:hover,
[data-testid="stDownloadButton"] > button:hover {
  transform: translateY(-2px);
  box-shadow: 0 7px 16px rgba(19,134,111,.12);
}
[data-testid="stSidebar"] [role="radiogroup"] label {
  transition: background-color .2s ease, color .2s ease,
              transform .2s cubic-bezier(.2,.7,.25,1);
}
[data-testid="stTabs"] button[role="tab"] {
  transition: color .18s ease, background-color .18s ease;
}
[data-testid="stTabs"] button[role="tab"]:hover {
  background: rgba(19,134,111,.055);
}
.mc-page-intro, .mc-profile-card, .mc-auth-hero {
  animation: mc-soft-reveal .48s cubic-bezier(.2,.7,.25,1) both;
}
@media (prefers-reduced-motion: reduce) {
  .main .block-container, .mc-mark, .mc-page-intro, .mc-profile-card, .mc-auth-hero {
    animation: none !important;
  }
  [data-testid="stMetric"],
  [data-testid="stVerticalBlockBorderWrapper"],
  [data-testid="stExpander"],
  [data-testid="stDataFrame"],
  .stButton > button,
  .stFormSubmitButton > button,
  [data-testid="stDownloadButton"] > button {
    transition: none !important;
    transform: none !important;
  }
}


/* ---- Shop typography and branded visual cards ---- */
.mc-shop-hero {
  position:relative; overflow:hidden; margin:0 0 1.35rem; padding:30px 34px;
  border:1px solid #d7e9e0; border-radius:22px;
  background:radial-gradient(circle at 88% 10%,rgba(76,196,151,.20),transparent 26%),
             linear-gradient(115deg,#ffffff 0%,#eef8f2 62%,#e5f4ed 100%);
  box-shadow:0 12px 32px rgba(20,59,53,.07);
}
.mc-shop-eyebrow { color:#13866f; font-size:.69rem; font-weight:800; letter-spacing:.16em; }
.mc-shop-hero h1 { margin:.45rem 0 .5rem; font-size:clamp(1.8rem,3.2vw,2.65rem); line-height:1.12; }
.mc-shop-hero p { max-width:690px; color:#617a72; font-size:1rem; line-height:1.7; margin-bottom:1rem; }
.mc-shop-trust { display:flex; flex-wrap:wrap; gap:9px; }
.mc-shop-trust span { border:1px solid #d3e8dd; background:rgba(255,255,255,.72); border-radius:30px; padding:6px 11px; color:#277461; font-size:.75rem; font-weight:700; }
.mc-shop-partner { color:#13866f; font-size:.82rem; font-weight:800; letter-spacing:.04em; margin-top:-5px; }
.mc-shop-hero h1, [data-testid="stVerticalBlockBorderWrapper"] h3 { letter-spacing:-.045em; }

</style>""", unsafe_allow_html=True)

# ---------------------------- API client ----------------------------
def error_message(response) -> str:
    """Return the API's human-readable error (FastAPI 'detail'), not the raw HTTP dump."""
    try:
        detail = response.json().get('detail')
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, list):  # FastAPI validation errors are a list of dicts
        detail = '; '.join(str(d.get('msg', d)) if isinstance(d, dict) else str(d) for d in detail)
    if detail:
        return str(detail)
    return f'The request could not be completed (HTTP {response.status_code}). Please try again.'


def api(method: str, path: str, *, data=None, params=None, auth=True, quiet=False):
    headers = {}
    token = st.session_state.get('token')
    if auth and token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        response = requests.request(
            method,
            f'{API_BASE}{path}',
            json=data,
            params=params,
            headers=headers,
            timeout=25,
        )
    except requests.RequestException as exc:
        st.error(f'Cannot reach MediCycle API at {API_BASE}. Details: {exc}')
        return None

    if response.status_code >= 400:
        if response.status_code == 401 and auth and token:
            # Access tokens expire (JWT_EXPIRE_MINUTES); send the user back to sign-in.
            st.session_state.clear()
            st.session_state['_clear_auth_cookie'] = True
            st.session_state['session_notice'] = 'Your session has expired. Please sign in again.'
            st.rerun()
        if quiet:
            return None
        st.error(error_message(response))
        return None

    if response.status_code == 204 or not response.content:
        return {}

    try:
        return response.json()
    except ValueError:
        return response.text


def records_table(records, title=None):
    if title:
        st.subheader(title)
    if not records:
        st.info('No records found yet.')
        return
    rows = []
    for item in records:
        if isinstance(item, dict):
            rows.append({k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v)) for k, v in item.items()})
        else:
            rows.append({'record': str(item)})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def refresh():
    st.rerun()


def login_screen(cookie_manager):
    st.markdown('<div class="mc-brand"><div class="mc-mark">♻</div><div class="mc-wordmark">MediCycle</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="mc-tagline">Responsible medicine returns · Reverse logistics · Verified disposal</div>', unsafe_allow_html=True)
    hero, forms = st.columns([0.88, 1.12], gap='large', vertical_alignment='center')
    with hero:
        st.markdown('''<div class="mc-auth-hero">
          <div><span class="mc-pill">A circular approach to care</span>
          <h2>Give unused medicines a safer next step.</h2>
          <p>MediCycle connects households, collection teams and authorized facilities to make medicine returns traceable and responsible.</p>
          <div class="mc-feature-list">
            <div class="mc-feature"><span>✓</span> Simple medicine return requests</div>
            <div class="mc-feature"><span>⌖</span> Trackable collection and handover</div>
            <div class="mc-feature"><span>♧</span> Verified receipt and disposal records</div>
          </div></div>
          <p style="font-size:.78rem;margin:34px 0 0;color:#b9ddd1">A more responsible cycle for medicines and communities.</p>
        </div>''', unsafe_allow_html=True)
    with forms:
        st.markdown('<div class="mc-section-label">Your MediCycle account</div>', unsafe_allow_html=True)
        st.markdown('### Welcome back')
        st.markdown('<div class="mc-subtle">Sign in to continue to your workspace.</div>', unsafe_allow_html=True)
        with st.container(border=True):
            with st.form('login_form'):
                identifier = st.text_input('Email or phone', placeholder='you@example.com')
                password = st.text_input('Password', type='password', placeholder='Enter your password')
                submitted = st.form_submit_button('Sign in →', use_container_width=True, type='primary')
            if submitted:
                result = api('POST', '/api/auth/login', data={'identifier': identifier, 'password': password}, auth=False)
                if result and result.get('accessToken'):
                    st.session_state.token = result['accessToken']
                    st.session_state.user = result['user']
                    _persist_access_token(cookie_manager, result['accessToken'])
                    refresh()
        with st.expander('New to MediCycle? Create a customer account', expanded=False):
            st.caption('Create an account to submit and track medicine returns.')
            with st.form('register_form'):
                full_name = st.text_input('Full name', placeholder='Your full name')
                email = st.text_input('Email', placeholder='you@example.com')
                phone = st.text_input('Phone', placeholder='Your phone number')
                new_password = st.text_input('Password (minimum 8 characters)', type='password', placeholder='Create a secure password')
                create = st.form_submit_button('Create account', use_container_width=True, type='primary')
            if create:
                payload = {'fullName': full_name, 'email': email or None, 'phone': phone or None, 'password': new_password}
                result = api('POST', '/api/auth/register', data=payload, auth=False)
                if result and result.get('accessToken'):
                    st.session_state.token = result['accessToken']
                    st.session_state.user = result['user']
                    _persist_access_token(cookie_manager, result['accessToken'])
                    refresh()
    st.markdown('<p class="mc-subtle" style="text-align:center;margin-top:24px">Facility staff and drivers sign in using accounts provisioned by an administrator.</p>', unsafe_allow_html=True)


def customer_recent_returns(records):
    """Render recent customer returns as compact cards without changing return data."""
    if not records:
        st.info('No return requests yet. Your submitted requests will appear here.')
        return

    status_styles = {
        'SUBMITTED': ('Submitted', '🟡'),
        'VERIFIED': ('Verified', '🔵'),
        'ASSIGNED': ('Driver assigned', '🟣'),
        'PICKED_UP': ('Picked up', '🔵'),
        'IN_TRANSIT': ('In transit', '🔵'),
        'ARRIVED': ('Arrived at facility', '🔵'),
        'RECEIVED': ('Received', '🟢'),
        'ACCEPTED': ('Accepted', '🟢'),
        'REJECTED': ('Rejected', '🔴'),
        'COMPLETED': ('Completed', '🟢'),
        'CANCELLED': ('Cancelled', '⚪'),
    }

    for item in records[:8]:
        return_id = str(item.get('returnId') or '')
        short_id = return_id[-8:].upper() if return_id else '—'
        raw_status = str(item.get('status') or 'UNKNOWN').upper()
        status_label, status_icon = status_styles.get(
            raw_status, (raw_status.replace('_', ' ').title(), '⚪')
        )
        method = str(item.get('returnMethod') or 'Return method not specified')
        method_label = method.replace('_', ' ').title()
        created = item.get('createdAt')
        if created:
            try:
                created_label = datetime.fromisoformat(str(created).replace('Z', '+00:00')).strftime('%d %b %Y · %I:%M %p')
            except (TypeError, ValueError):
                created_label = str(created).replace('T', ' ')[:16]
        else:
            created_label = 'Date unavailable'

        with st.container(border=True):
            left, right = st.columns([3, 1])
            left.markdown(f"**Return #{short_id}**")
            left.caption(f"{method_label} · {created_label}")
            if item.get('requestNotes'):
                left.write(str(item.get('requestNotes')))
            if raw_status == 'REJECTED' and item.get('rejectionReason'):
                left.caption(f"Reason: {item.get('rejectionReason')}")
            right.markdown(f"**{status_icon} {status_label}**")


def customer_dashboard():
    """Customer overview: presentation-only redesign using existing read endpoints."""
    profile = api('GET', '/api/users/me')
    wallet = api('GET', '/api/wallet')
    returns = api('GET', '/api/returns')
    returns = returns if isinstance(returns, list) else []

    first_name = str((profile or {}).get('fullName') or 'there').strip().split(' ')[0]
    balance = (wallet or {}).get('availableBalance', '—')
    active_statuses = {'SUBMITTED', 'VERIFIED', 'ASSIGNED', 'PICKED_UP', 'IN_TRANSIT', 'ARRIVED', 'RECEIVED'}
    completed_count = sum(str(item.get('status') or '').upper() == 'COMPLETED' for item in returns)
    active_count = sum(str(item.get('status') or '').upper() in active_statuses for item in returns)

    st.markdown(
        '<section style="padding:28px 30px;border-radius:22px;background:linear-gradient(115deg,#103f36 0%,#08765f 65%,#19a17e 100%);'
        'box-shadow:0 16px 36px rgba(13,83,67,.16);margin:0 0 22px;color:#fff">'
        '<div style="font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;font-weight:800;color:#b8ead8">CUSTOMER OVERVIEW</div>'
        '<div style="font-family:Manrope,sans-serif;font-size:clamp(1.65rem,3vw,2.35rem);font-weight:800;letter-spacing:-.045em;margin:8px 0 5px;color:#fff">'
        'Welcome back, ' + first_name + '.</div>'
        '<div style="font-size:.95rem;color:#d7f1e7;max-width:650px;line-height:1.65">'
        'Your medicine returns, collection activity and MediCredits — all in one place.</div>'
        '</section>',
        unsafe_allow_html=True,
    )

    st.markdown('#### Your activity at a glance')
    k1, k2, k3, k4 = st.columns(4)
    k1.metric('MediCredits', balance, help='Your currently available reward balance.')
    k2.metric('Return requests', len(returns))
    k3.metric('In progress', active_count)
    k4.metric('Completed', completed_count)

    left, right = st.columns([1.35, 1], gap='large')
    with left:
        st.markdown('#### Recent returns')
        customer_recent_returns(returns)
    with right:
        with st.container(border=True):
            st.markdown('#### Return journey')
            st.caption('Follow the progress of your medicine returns.')
            stages = [
                ('Submitted', 'SUBMITTED'),
                ('Verified', 'VERIFIED'),
                ('Collected / in transit', 'IN_TRANSIT'),
                ('Received', 'RECEIVED'),
                ('Completed', 'COMPLETED'),
            ]
            if returns:
                statuses = [str(item.get('status') or '').upper() for item in returns]
                for label, status in stages:
                    count = sum(value == status for value in statuses)
                    st.write(f'**{label}**')
                    st.progress(min(count / max(len(returns), 1), 1.0), text=f'{count} request(s)')
            else:
                st.info('Your return activity will appear here after you submit your first request.')
            st.divider()
            st.markdown('**MediCredits tip**')
            st.caption('Credits are added only after the facility physically receives and verifies an entire return request.')

    if profile and profile.get('accountStatus'):
        st.caption(f"Account status: {str(profile.get('accountStatus')).replace('_', ' ').title()}")


def render_expired_medicine_bucket(bucket, key_prefix="expired_bucket"):
    """Show expired tracked medicines as selectable cards and submit through the existing bucket API."""
    st.subheader("Expired medicines")
    st.caption("Medicines past their recorded expiry date are collected here. Select the entries you want to return.")
    if not bucket:
        st.success("Your expired-medicine bucket is empty. Expired tracked medicines will appear here automatically.")
        return

    total_units = sum(int(item.get("quantity") or 0) for item in bucket)
    metric_a, metric_b = st.columns(2)
    metric_a.metric("Expired entries", len(bucket))
    metric_b.metric("Units awaiting return", total_units)

    for item in bucket:
        name = " ".join(part for part in [str(item.get("name") or "Medicine"), str(item.get("strength") or "")] if part).strip()
        with st.container(border=True):
            name_col, qty_col, expiry_col = st.columns([2.2, 1, 1.25])
            name_col.markdown(f"**{name}**")
            name_col.caption(f"{item.get('sourcePlatform') or 'Tracked medicine'} · Batch {item.get('batchNumber') or '—'}")
            qty_col.metric("Quantity", item.get("quantity") or 0)
            expiry_col.metric("Expired on", str(item.get("expiresOn") or "—")[:10])
            if item.get("isDemo"):
                st.caption("Illustrative demo record")

    addresses = api("GET", "/api/users/me/addresses") or []
    facilities = api("GET", "/api/facilities") or []
    slots = api("GET", "/api/pickup-slots") or []
    with st.form(f"{key_prefix}_submit_form"):
        st.markdown("**Select medicines to include in a return**")
        selected_bucket_ids = []
        for item in bucket:
            label = f"{item.get('name')} {item.get('strength') or ''} · Qty {item.get('quantity')} · Expired {item.get('expiresOn') or '—'}"
            if st.checkbox(label, value=True, key=f"{key_prefix}_select_{item.get('bucketItemId')}"):
                selected_bucket_ids.append(item.get("bucketItemId"))

        method = st.radio("Return method", ["DOORSTEP_PICKUP", "PHARMACY_DROPOFF"],
            format_func=lambda value: "Doorstep pickup" if value == "DOORSTEP_PICKUP" else "Direct facility drop-off",
            horizontal=True, key=f"{key_prefix}_method")
        address_map = {
            f"{item.get('addressLabel') or 'Saved address'} · {item.get('addressLine')}, {item.get('city')}": item.get("addressId")
            for item in addresses
        }
        facility_map = {
            f"{item.get('facilityName')} · {item.get('address') or item.get('city') or ''}": item.get("facilityId")
            for item in facilities
        }
        slot_map = {}
        for item in slots:
            if str(item.get("slotStatus", "")).upper() not in ("AVAILABLE", "OPEN"):
                continue
            if int(item.get("bookedCount") or 0) >= int(item.get("capacity") or 0):
                continue
            day = str(item.get("slotDate") or "")[:10]
            start = str(item.get("startTime") or "").split("T")[-1][:5]
            end = str(item.get("endTime") or "").split("T")[-1][:5]
            slot_map[f"{day} · {start}–{end}"] = item.get("pickupSlotId")

        address_choice = st.selectbox("Pickup address", list(address_map), key=f"{key_prefix}_address") if address_map else None
        facility_choice = st.selectbox("Drop-off facility", list(facility_map), key=f"{key_prefix}_facility") if method == "PHARMACY_DROPOFF" and facility_map else None
        slot_choice = st.selectbox("Pickup slot", list(slot_map), key=f"{key_prefix}_slot") if method == "DOORSTEP_PICKUP" and slot_map else None
        submit = st.form_submit_button("Submit selected expired medicines", type="primary",
            use_container_width=True, disabled=not selected_bucket_ids)

    if submit:
        if method == "DOORSTEP_PICKUP" and (not address_choice or not slot_choice):
            st.error("A saved address and available pickup slot are required.")
        elif method == "PHARMACY_DROPOFF" and not facility_choice:
            st.error("Select an operational drop-off facility.")
        else:
            result = api("POST", "/api/return-bucket/submit", data={
                "bucketItemIds": selected_bucket_ids,
                "addressId": address_map.get(address_choice) if address_choice else None,
                "returnMethod": method,
                "pickupSlotId": slot_map.get(slot_choice) if slot_choice else None,
                "facilityId": facility_map.get(facility_choice) if facility_choice else None,
            })
            if result:
                st.success(f"Return request submitted with {result.get('submittedItems')} expired medicine entries.")
                st.rerun()


def customer_my_medicines():
    st.title("My Medicines")
    st.caption("Track medicines purchased from pharmacy apps. Add details from your order or medicine packaging.")
    st.info("Tata 1mg and PharmEasy are source labels only; MediCycle does not currently import live order history. Near-expiry means 30 days or less. Expired means the expiry date is before today.")
    # Synchronization is an explicit POST operation; GET endpoints remain read-only.
    api("POST", "/api/return-bucket/sync")
    inventory = api("GET", "/api/my-medicines") or []
    bucket = api("GET", "/api/return-bucket") or []
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Tracked",len(inventory))
    c2.metric("Near expiry",sum(x.get("expiryStatus")=="NEAR_EXPIRY" for x in inventory))
    c3.metric("Expired",sum(x.get("expiryStatus")=="EXPIRED" for x in inventory))
    c4.metric("Return bucket",len(bucket))
    tab_inventory,tab_add,tab_bucket=st.tabs(["Inventory","Add purchase","Return bucket"])
    with tab_inventory:
        if inventory:
            for item in inventory:
                with st.container(border=True):
                    left,right=st.columns([3,1])
                    left.markdown(f"**{item.get('name')} {item.get('strength') or ''}**")
                    left.caption(f"{item.get('sourcePlatform') or 'Manually added'} · Order {item.get('externalOrderId') or '—'} · Batch {item.get('batchNumber') or '—'}")
                    left.write(f"Quantity: {item.get('quantity')} · Expiry: {item.get('expiresOn') or 'Not recorded'}")
                    if item.get("isDemo"): left.caption("Illustrative demo record")
                    state=item.get("expiryStatus")
                    right.metric("Status",state.replace("_"," ").title() if state else "Unknown")
        else: st.info("No medicines tracked yet. Add a purchase or load illustrative demo records.")
        if st.button("Load demo medicines",type="secondary"):
            result=api("POST","/api/my-medicines/demo")
            if result: st.success(result.get("message","Demo records loaded")); st.rerun()
    with tab_add:
        catalogue=api("GET","/api/medicines/catalogue",params={"limit":500}) or []
        options={f"{m.get('name')} {m.get('strength') or ''} — {m.get('dosageForm') or ''}":m.get("medicineId") for m in catalogue}
        with st.form("add_tracked_medicine"):
            source=st.selectbox("Purchased from",["TATA_1MG","PHARMEASY"],format_func=lambda x:"Tata 1mg" if x=="TATA_1MG" else "PharmEasy")
            choice=st.selectbox("Medicine",list(options),disabled=not options)
            batch_no=st.text_input("Batch number")
            expiry=st.date_input("Expiry date")
            manufactured=st.date_input("Manufacturing date (optional)",value=None)
            quantity=st.number_input("Quantity",min_value=1,max_value=10000,value=1)
            purchase=st.date_input("Purchase date",value=datetime.now().date())
            order=st.text_input("Order ID (optional)")
            packaging=st.selectbox("Packaging state",["SEALED","INTACT","OPENED","DAMAGED","UNKNOWN"])
            save=st.form_submit_button("Add to My Medicines",type="primary")
        if save:
            if not options or not batch_no.strip(): st.error("Select a catalogue medicine and enter its batch number.")
            else:
                result=api("POST","/api/my-medicines",data={"medicineId":options[choice],"batchNumber":batch_no.strip(),"expiresOn":expiry.isoformat(),"manufacturedOn":manufactured.isoformat() if manufactured else None,"quantity":int(quantity),"purchaseDate":purchase.isoformat(),"sourcePlatform":source,"externalOrderId":order or None,"packagingState":packaging})
                if result: st.success("Medicine added to your tracker."); st.rerun()
    with tab_bucket:
        render_expired_medicine_bucket(bucket, key_prefix="my_medicines_bucket")


def customer_medicine_apps():
    st.title("Medicine Apps")
    st.caption("Prototype workspace for recording medicine purchases from pharmacy apps.")
    st.info("This is a MediCycle prototype: no pharmacy account is connected and no orders are imported. Add sample or manually recorded purchase details under the app they came from.")

    catalogue = api("GET", "/api/medicines/catalogue", params={"limit": 500}) or []
    options = {
        f"{m.get('name')} {m.get('strength') or ''} — {m.get('dosageForm') or ''}": m.get("medicineId")
        for m in catalogue
    }
    inventory = api("GET", "/api/my-medicines") or []

    if st.button("Load sample purchases for both apps", type="secondary", use_container_width=True):
        result = api("POST", "/api/my-medicines/demo")
        if result:
            st.success(result.get("message", "Sample purchases loaded."))
            st.rerun()

    app_tabs = st.tabs(["Tata 1mg", "PharmEasy"])
    apps = [
        ("TATA_1MG", "Tata 1mg", "Record purchases you want to track from Tata 1mg."),
        ("PHARMEASY", "PharmEasy", "Record purchases you want to track from PharmEasy."),
    ]

    for tab, (source_code, source_label, description) in zip(app_tabs, apps):
        with tab:
            if source_code == "TATA_1MG":
                st.markdown("""
                <div style="display:flex;align-items:center;gap:14px;padding:14px 18px;border:1px solid #f0d5d5;border-radius:16px;background:#fff;margin:4px 0 18px">
                  <div style="width:62px;height:62px;border-radius:14px;background:#e53935;color:#fff;display:grid;place-items:center;font-size:22px;font-weight:900;letter-spacing:-1px">1mg</div>
                  <div><div style="font-size:1.28rem;font-weight:800;color:#263238">Tata 1mg</div><div style="font-size:.82rem;color:#75838b">Medicine purchase source</div></div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="display:flex;align-items:center;gap:14px;padding:14px 18px;border:1px solid #e6dcf6;border-radius:16px;background:#fff;margin:4px 0 18px">
                  <div style="width:62px;height:62px;border-radius:14px;background:#6039a5;color:#fff;display:grid;place-items:center;font-size:25px;font-weight:900">P<span style="color:#a8e35b">+</span></div>
                  <div><div style="font-size:1.28rem;font-weight:800;color:#263238">PharmEasy</div><div style="font-size:.82rem;color:#75838b">Medicine purchase source</div></div>
                </div>
                """, unsafe_allow_html=True)
            st.caption(description)
            app_inventory = [x for x in inventory if x.get("sourcePlatform") == source_code]
            total_qty = sum(int(x.get("quantity") or 0) for x in app_inventory)
            m1, m2, m3 = st.columns(3)
            m1.metric("Recorded purchases", len(app_inventory))
            m2.metric("Total units", total_qty)
            m3.metric("Expired", sum(x.get("expiryStatus") == "EXPIRED" for x in app_inventory))

            with st.expander(f"Add {source_label} purchase", expanded=True):
                with st.form(f"add_purchase_{source_code.lower()}"):
                    choice = st.selectbox("Medicine", list(options), disabled=not options, key=f"medicine_{source_code.lower()}")
                    batch_no = st.text_input("Batch number", key=f"batch_{source_code.lower()}")
                    expiry = st.date_input("Expiry date", key=f"expiry_{source_code.lower()}")
                    manufactured = st.date_input("Manufacturing date (optional)", value=None, key=f"manufactured_{source_code.lower()}")
                    quantity = st.number_input("Quantity", min_value=1, max_value=10000, value=1, key=f"quantity_{source_code.lower()}")
                    purchase = st.date_input("Purchase date", value=datetime.now().date(), key=f"purchase_{source_code.lower()}")
                    order = st.text_input("Order ID (optional)", key=f"order_{source_code.lower()}")
                    packaging = st.selectbox("Packaging state", ["SEALED", "INTACT", "OPENED", "DAMAGED", "UNKNOWN"], key=f"packaging_{source_code.lower()}")
                    save = st.form_submit_button("Save purchase", type="primary", disabled=not options)
                if save:
                    if not options or not batch_no.strip():
                        st.error("Select a catalogue medicine and enter its batch number.")
                    else:
                        result = api("POST", "/api/my-medicines", data={
                            "medicineId": options[choice],
                            "batchNumber": batch_no.strip(),
                            "expiresOn": expiry.isoformat(),
                            "manufacturedOn": manufactured.isoformat() if manufactured else None,
                            "quantity": int(quantity),
                            "purchaseDate": purchase.isoformat(),
                            "sourcePlatform": source_code,
                            "externalOrderId": order.strip() or None,
                            "packagingState": packaging,
                        })
                        if result:
                            st.success(f"Purchase saved under {source_label}.")
                            st.rerun()

            st.markdown(f"**Your {source_label} records**")
            if app_inventory:
                for item in app_inventory:
                    with st.container(border=True):
                        left, right = st.columns([3, 1])
                        left.markdown(f"**{item.get('name')} {item.get('strength') or ''}**")
                        left.caption(f"Order {item.get('externalOrderId') or '—'} · Batch {item.get('batchNumber') or '—'}")
                        left.write(f"Quantity: {item.get('quantity')} · Purchase date: {item.get('purchaseDate') or '—'} · Expiry: {item.get('expiresOn') or 'Not recorded'}")
                        if item.get("isDemo"):
                            left.caption("Illustrative demo record")
                        state = item.get("expiryStatus")
                        right.metric("Status", state.replace("_", " ").title() if state else "Unknown")
            else:
                st.info(f"No {source_label} purchases have been recorded yet. Use the form above to add prototype data.")

def customer_returns():
    st.title("Medicine returns")
    st.caption("Request a safe collection for your medicines and follow its progress.")
    refresh_col, _ = st.columns([1, 5])
    if refresh_col.button("↻ Refresh status", key="refresh_returns_status"):
        st.rerun()

    confirmation = st.session_state.get("return_confirmation")
    if confirmation:
        with st.container(border=True):
            st.success("Your return request has been verified")
            if confirmation.get("isDemo"):
                st.info("DEMO REQUEST · Simulated pickup workflow")
            st.markdown("### Request confirmed")
            st.write(confirmation.get("message") or "Your request passed the initial checks.")
            c1, c2 = st.columns(2)
            c1.metric("Medicines submitted", confirmation.get("submittedItems", 0))
            c2.metric(
                "Request status",
                "Driver assigned" if confirmation.get("pickupAssigned") else (
                    "Awaiting driver" if confirmation.get("returnMethod") == "DOORSTEP_PICKUP" else "Ready for drop-off"
                ),
            )
            assignment = confirmation.get("assignment") or {}
            if assignment.get("driverName"):
                st.info(f"Your pickup driver is **{assignment['driverName']}**.")
                if confirmation.get("isDemo"):
                    st.success("Your demo driver is expected at your location in about 10 minutes.")
            elif confirmation.get("returnMethod") == "DOORSTEP_PICKUP":
                st.warning("Your request is verified. We are finding an available driver and will update the assignment shortly.")
            else:
                st.info("Your request is verified. Please take the medicines to the facility you selected.")
            if st.button("Create another return request", type="secondary"):
                st.session_state.pop("return_confirmation", None)
                st.rerun()

    # Keep the expired-medicine bucket available without pushing the return
    # form below a long list. Customers can expand it only when they need it.
    api("POST", "/api/return-bucket/sync")
    expired_bucket = api("GET", "/api/return-bucket") or []
    expired_count = len(expired_bucket)
    with st.expander(
        f"Expired medicines ready to return · {expired_count}",
        expanded=False,
    ):
        if expired_bucket:
            st.caption("Review the medicines detected as expired. Expand this section whenever you want to inspect or submit them.")
            render_expired_medicine_bucket(expired_bucket, key_prefix="returns_bucket")
        else:
            st.info("No expired medicines are currently waiting in your return bucket.")

    st.markdown("### Start a return")
    st.caption("Create a new medicine return or check the progress of an earlier request.")
    tab_new, tab_history = st.tabs(["＋ New return", "Return history"])
    with tab_new:
        addresses = api("GET", "/api/users/me/addresses") or []
        facilities = api("GET", "/api/facilities") or []
        slots = api("GET", "/api/pickup-slots") or []
        medicine_catalogue = api("GET", "/api/medicines/catalogue", params={"limit": 100}) or []

        st.markdown("#### 1. Choose how to return")
        with st.form("return_form"):
            request_mode = st.radio(
                "Request type",
                ["STANDARD", "DEMO"],
                format_func=lambda x: "Standard request" if x == "STANDARD" else "Demo request (simulated 10-minute pickup)",
                horizontal=True,
            )
            if request_mode == "DEMO":
                method = "DOORSTEP_PICKUP"
                st.info("Demo mode uses a dedicated demo driver and does not reserve a real pickup slot.")
            else:
                method = st.radio(
                    "Return method",
                    ["DOORSTEP_PICKUP", "PHARMACY_DROPOFF"],
                    format_func=lambda x: "Doorstep pickup" if x == "DOORSTEP_PICKUP" else "Drop off at a facility",
                    horizontal=True,
                )

            address_map = {}
            for index, address in enumerate(addresses, start=1):
                label = " · ".join(
                    part for part in [
                        address.get("addressLabel") or f"Saved address {index}",
                        address.get("addressLine"),
                        address.get("city"),
                    ] if part
                )
                address_map[label] = address.get("addressId")

            facility_map = {}
            for facility in facilities:
                label = " · ".join(
                    part for part in [facility.get("facilityName"), facility.get("address"), facility.get("city")] if part
                )
                facility_map[label] = facility.get("facilityId")

            slot_map = {}
            for index, slot in enumerate(slots, start=1):
                if str(slot.get("slotStatus", "")).upper() not in ("AVAILABLE", "OPEN"):
                    continue
                if int(slot.get("bookedCount") or 0) >= int(slot.get("capacity") or 0):
                    continue
                day = str(slot.get("slotDate") or "")
                start_time = str(slot.get("startTime") or "").split("T")[-1][:5]
                end_time = str(slot.get("endTime") or "").split("T")[-1][:5]
                label = f"{day} · {start_time}–{end_time}"
                if label in slot_map:
                    label = f"{label} · Option {index}"
                slot_map[label] = slot.get("pickupSlotId")

            address_choice = None
            facility_choice = None
            slot_choice = None
            if method == "DOORSTEP_PICKUP":
                st.markdown("#### 2. Pickup details")
                if address_map:
                    address_choice = st.selectbox("Pickup address", list(address_map))
                else:
                    st.warning("Add a saved pickup address in Profile & addresses before requesting collection.")
                if request_mode == "DEMO":
                    st.caption("Demo courier arrival estimate: about 10 minutes (simulated).")
                elif slot_map:
                    slot_choice = st.selectbox("Preferred pickup window", list(slot_map))
                else:
                    st.warning("There are currently no available pickup windows.")
            else:
                st.markdown("#### 2. Choose a drop-off facility")
                if facility_map:
                    facility_choice = st.selectbox("MediCycle facility", list(facility_map))
                else:
                    st.warning("No operational drop-off facilities are currently available.")

            st.markdown("#### 3. Add medicines")
            medicine_map = {}
            for medicine in medicine_catalogue:
                label = " ".join(
                    part for part in [
                        medicine.get("name"),
                        medicine.get("strength"),
                        medicine.get("dosageForm"),
                    ] if part
                )
                medicine_map[label] = medicine.get("medicineId")

            item_count = st.number_input(
                "Number of different medicines",
                min_value=1,
                max_value=10,
                value=1,
                step=1,
            )
            selected_items = []
            for index in range(int(item_count)):
                st.markdown(f"**Medicine {index + 1}**")
                medicine_choice = st.selectbox(
                    "Medicine",
                    ["Choose a medicine"] + list(medicine_map),
                    key=f"return_medicine_{index}",
                    disabled=not medicine_map,
                )
                qty = st.number_input(
                    "Quantity",
                    min_value=1,
                    max_value=10000,
                    value=1,
                    key=f"return_quantity_{index}",
                )
                packaging = st.selectbox(
                    "Packaging condition",
                    ["SEALED", "INTACT", "DAMAGED", "OPENED", "UNKNOWN"],
                    format_func=lambda x: x.replace("_", " ").title(),
                    key=f"return_packaging_{index}",
                )
                selected_items.append({
                    "medicineId": medicine_map.get(medicine_choice),
                    "quantity": int(qty),
                    "packagingCondition": packaging,
                })

            notes = st.text_area("Additional information (optional)", placeholder="Anything the pickup driver or facility should know?")
            submit = st.form_submit_button(
                "Verify and submit return",
                type="primary",
                use_container_width=True,
            )

        if submit:
            if any(not item.get("medicineId") for item in selected_items):
                st.error("Please select a medicine for every entry.")
            elif method == "DOORSTEP_PICKUP" and (not address_choice or (request_mode != "DEMO" and not slot_choice)):
                st.error("A saved pickup address and the required pickup window are required.")
            elif method == "PHARMACY_DROPOFF" and not facility_choice:
                st.error("Please select an operational drop-off facility.")
            else:
                payload = {
                    "addressId": address_map.get(address_choice) if address_choice else None,
                    "returnMethod": method,
                    "isDemo": request_mode == "DEMO",
                    "pickupSlotId": slot_map.get(slot_choice) if slot_choice else None,
                    "facilityId": facility_map.get(facility_choice) if facility_choice else None,
                    "requestNotes": notes.strip() or None,
                    "items": selected_items,
                }
                result = api("POST", "/api/returns", data=payload)
                if result:
                    st.session_state["return_confirmation"] = result
                    st.rerun()

        st.caption("Your request is checked before a driver is assigned. Final medicine inspection and MediCredits approval happen after the facility receives the return.")

    with tab_history:
        history = api("GET", "/api/returns") or []
        # Cancelled requests remain in the database for audit/history, but are hidden
        # from the customer's active Return History list.
        visible_history = [
            record for record in history
            if str(record.get("status") or "SUBMITTED").upper() != "CANCELLED"
        ]
        if not visible_history:
            st.info("You have no active return requests.")
        else:
            for index, record in enumerate(visible_history):
                status_value = str(record.get("status") or "SUBMITTED").upper()
                status_labels = {
                    "VERIFIED": "Verified",
                    "ASSIGNED": "Driver assigned",
                    "ACCEPTED": "Accepted by facility",
                    "REJECTED": "Rejected by facility",
                    "PICKED_UP": "Picked up",
                    "IN_TRANSIT": "On the way",
                    "ARRIVED": "Arrived at facility",
                    "RECEIVED": "Received by facility",
                    "COMPLETED": "Completed",
                    "SUBMITTED": "Submitted",
                }
                method_label = "Doorstep pickup" if record.get("returnMethod") == "DOORSTEP_PICKUP" else "Facility drop-off"
                with st.container(border=True):
                    left, right = st.columns([3, 1])
                    left.markdown(f"**Return request {len(visible_history) - index}**")
                    left.caption(method_label)
                    left.write(f"Status: **{status_labels.get(status_value, status_value.replace('_', ' ').title())}**")
                    created = record.get("createdAt")
                    if created:
                        left.caption(f"Submitted {str(created).replace('T', ' ')[:16]}")
                    is_demo = str(record.get("requestNotes") or "").startswith("[DEMO REQUEST]")
                    if is_demo and status_value not in {"COMPLETED", "CANCELLED", "REJECTED"}:
                        left.caption("Demo simulation: auto-completes 10 minutes after submission.")
                        if right.button("Complete demo now", key=f"complete_demo_{record.get('returnId')}", type="primary"):
                            result = api("POST", f"/api/returns/{record.get('returnId')}/demo-complete")
                            if result:
                                st.success(f"Demo completed. {result.get('creditsAwarded', '0')} MediCredits awarded.")
                                st.rerun()
                    elif is_demo and status_value == "COMPLETED":
                        left.caption("Demo completed · 10 credits awarded per medicine unit.")
                    if right.button("View details", key=f"view_return_{record.get('returnId')}"):
                        st.session_state["selected_return_detail"] = record.get("returnId")
                        st.rerun()
                    if status_value in {"SUBMITTED", "VERIFIED", "ASSIGNED"}:
                        if right.button("Cancel request", key=f"cancel_return_{record.get('returnId')}"):
                            st.session_state["confirm_cancel_return_id"] = record.get("returnId")
                            st.rerun()

        pending_cancel_id = st.session_state.get("confirm_cancel_return_id")
        if pending_cancel_id:
            st.warning("Cancel this return request? The pickup reservation will be released. This action cannot be undone.")
            confirm_col, keep_col = st.columns(2)
            if confirm_col.button("Yes, cancel request", type="primary", key="confirm_cancel_return"):
                result = api("POST", f"/api/returns/{pending_cancel_id}/cancel")
                if result:
                    st.session_state.pop("confirm_cancel_return_id", None)
                    st.success(result.get("message", "Return request cancelled."))
                    st.rerun()
            if keep_col.button("Keep request", key="keep_return_request"):
                st.session_state.pop("confirm_cancel_return_id", None)
                st.rerun()

        selected_return_id = st.session_state.get("selected_return_detail")
        if selected_return_id:
            detail = api("GET", f"/api/returns/{selected_return_id}")
            if detail:
                st.markdown("#### Return details")
                request = detail.get("return") or {}
                st.write(f"**Status:** {str(request.get('status', '—')).replace('_', ' ').title()}")
                st.write(f"**Method:** {'Doorstep pickup' if request.get('returnMethod') == 'DOORSTEP_PICKUP' else 'Facility drop-off'}")
                for item in detail.get("items", []):
                    st.write(f"• Medicine entry · Quantity {item.get('quantity', '—')} · Inspection {str(item.get('inspectionStatus', 'PENDING')).replace('_', ' ').title()}")
                if st.button("Close details", key="close_return_detail"):
                    st.session_state.pop("selected_return_detail", None)
                    st.rerun()

def customer_wallet():
    st.title('Wallet & rewards')
    notice = st.session_state.pop('redeem_notice', None)
    if notice:
        st.success(notice)

    wallet = api('GET', '/api/wallet')
    balance = float(wallet.get('availableBalance', 0) or 0) if wallet else None
    transactions = api('GET', '/api/wallet/transactions') or []
    welcome_status = api('GET', '/api/wallet/welcome-bonus-status') or {}
    welcome_claimed = bool(welcome_status.get('claimed'))

    top_balance, top_activity = st.columns([1.25, 1], gap='large')
    with top_balance:
        with st.container(border=True):
            st.caption('YOUR AVAILABLE BALANCE')
            st.metric('MediCredits', wallet.get('availableBalance', '—') if wallet else '—')
            st.progress(min(max((balance or 0) / 500, 0.0), 1.0), text='Progress towards 500 credits')
    with top_activity:
        with st.container(border=True):
            st.caption('WALLET ACTIVITY')
            credits_earned = sum(float(t.get('amount') or 0) for t in transactions if str(t.get('transactionType', '')).upper() == 'CREDIT')
            credits_spent = sum(float(t.get('amount') or 0) for t in transactions if str(t.get('transactionType', '')).upper() == 'DEBIT')
            earned_col, spent_col = st.columns(2)
            earned_col.metric('Earned', f'{credits_earned:g}')
            spent_col.metric('Redeemed', f'{credits_spent:g}')

    st.subheader('Your welcome reward')
    with st.container(border=True):
        welcome_left, welcome_right = st.columns([3, 1], vertical_alignment='center')
        with welcome_left:
            st.markdown('### 🎁 100 MediCredits')
            st.write('A one-time welcome reward for eligible customer accounts.')
            st.caption('Credits are added to your wallet and recorded in your transaction history.')
        with welcome_right:
            if welcome_claimed:
                st.info('Already claimed')
            elif st.button('Claim reward', key='claim_welcome_bonus', type='primary', use_container_width=True):
                result = api('POST', '/api/wallet/claim-welcome-bonus')
                if result:
                    st.session_state['redeem_notice'] = (
                        f"Welcome reward claimed: {result.get('creditedAmount', '100')} MediCredits added. "
                        f"New balance: {result.get('availableBalance', '—')}."
                    )
                    st.rerun()

    rewards = api('GET', '/api/rewards') or []
    st.divider()
    catalogue_tab, activity_tab = st.tabs(['🎁 Redeem rewards', '↗ Transaction activity'])

    with catalogue_tab:
        st.subheader('Reward catalogue')
        if rewards:
            search_col, sort_col = st.columns([2, 1])
            search_term = search_col.text_input('Search rewards', placeholder='Search by reward or partner…', key='reward_search').strip().lower()
            sort_by = sort_col.selectbox('Sort by', ['Credits: low to high', 'Credits: high to low', 'Partner name'], key='reward_sort')
            filtered = [
                reward for reward in rewards
                if search_term in str(reward.get('title', '')).lower()
                or search_term in str(reward.get('partnerName', '')).lower()
                or search_term in str(reward.get('description', '')).lower()
            ]
            if sort_by == 'Credits: high to low':
                filtered.sort(key=lambda item: float(item.get('creditsRequired') or 0), reverse=True)
            elif sort_by == 'Partner name':
                filtered.sort(key=lambda item: str(item.get('partnerName') or '').lower())
            else:
                filtered.sort(key=lambda item: float(item.get('creditsRequired') or 0))

            st.caption(f'{len(filtered)} of {len(rewards)} rewards')
            if filtered:
                for reward in filtered:
                    required = float(reward.get('creditsRequired') or 0)
                    affordable = balance is not None and balance >= required
                    with st.container(border=True):
                        title_col, cost_col = st.columns([3, 1], vertical_alignment='center')
                        with title_col:
                            st.markdown(f"**{reward.get('title', 'Reward')}**")
                            st.caption(f"Partner · {reward.get('partnerName', '—')}")
                        with cost_col:
                            st.metric('Cost', f'{required:g} MC')
                        if reward.get('description'):
                            st.write(reward.get('description'))
                        if balance is None:
                            st.warning('Wallet balance is unavailable. Refresh before redeeming.')
                        elif not affordable:
                            st.caption(f'You need {required - balance:g} more MediCredits.')
                        if st.button(
                            'Redeem reward',
                            key=f"redeem_{reward.get('rewardId')}",
                            disabled=not affordable,
                            type='primary' if affordable else 'secondary',
                            use_container_width=True,
                        ):
                            result = api('POST', '/api/reward-redemptions', data={'rewardId': reward.get('rewardId')})
                            if result:
                                redemption = result.get('redemption', {}) if isinstance(result, dict) else {}
                                st.session_state['redeem_notice'] = (
                                    f"Reward redeemed. Your code: {redemption.get('redemptionCode', '—')}. "
                                    f"Remaining MediCredits: {result.get('remainingBalance', '—')}."
                                )
                                st.rerun()
            else:
                st.info('No rewards match that search. Try another name or partner.')
        else:
            st.info('No rewards are currently available. Check back later.')

    with activity_tab:
        st.subheader('Recent wallet activity')
        if transactions:
            for transaction in transactions:
                tx_type = str(transaction.get('transactionType', '')).upper()
                amount = float(transaction.get('amount') or 0)
                icon = '＋' if tx_type == 'CREDIT' else '−'
                label = 'Credits added' if tx_type == 'CREDIT' else 'Credits redeemed' if tx_type == 'DEBIT' else tx_type
                with st.container(border=True):
                    left, right = st.columns([3, 1], vertical_alignment='center')
                    left.markdown(f"**{label}**")
                    left.caption(transaction.get('description') or transaction.get('referenceCode') or 'Wallet transaction')
                    right.metric('Amount', f"{icon}{amount:g} MC")
        else:
            st.info('Your wallet activity will appear here.')

def customer_shop():
    """Render the simulated MediCycle coupon shop with branded pharmacy imagery."""
    st.markdown(
        """
        <section class="mc-shop-hero">
          <div class="mc-shop-eyebrow">MEDICYCLE REWARDS STORE</div>
          <h1>Good choices. Better rewards.</h1>
          <p>Use your MediCredits to unlock simulated pharmacy-app coupons and keep your medicine journey moving responsibly.</p>
          <div class="mc-shop-trust"><span>✦ Earn credits</span><span>✦ Redeem rewards</span><span>✦ Track every coupon</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.warning(
        "Demo mode: these are internal test vouchers, not valid Tata 1mg or PharmEasy promo codes. "
        "No real discount is applied to purchases."
    )

    wallet = api("GET", "/api/wallet")
    balance = float(wallet.get("availableBalance", 0) or 0) if wallet else None
    rewards = api("GET", "/api/rewards") or []
    issued = api("GET", "/api/my-reward-redemptions") or []

    shop_tab, coupons_tab = st.tabs(["Coupon shop", "My coupons"])
    with shop_tab:
        if balance is not None:
            st.metric("Available MediCredits", f"{balance:,.0f} MC")
        partner_filter = st.selectbox(
            "Pharmacy app",
            ["All apps", "Tata 1mg", "PharmEasy"],
            key="shop_partner_filter",
        )

        # Brand artwork is presentation-only; reward data and redemption API stay unchanged.
        partners = {
            "Tata 1mg": {
                "image": "https://dmlib.airindia.com/adobe/assets/urn%3Aaaid%3Aaem%3A8013b25a-37b8-48f5-82aa-b2777ee691be/as/1mg-about.webp",
                "alt": "Tata 1mg medicine and healthcare app artwork",
                "class": "mc-shop-brand-tata",
                "subtitle": "Your everyday health essentials",
            },
            "PharmEasy": {
                "image": "https://static.wixstatic.com/media/7831a0_6bf395e55eb943849a604f63ea5456a9~mv2.png/v1/fill/w_384%2Ch_384%2Cal_c/25.png",
                "alt": "PharmEasy brand logo",
                "class": "mc-shop-brand-pharmeasy",
                "subtitle": "Healthcare, made a little easier",
            },
        }
        if not rewards:
            st.info("No demo coupons are available yet. The shop catalogue may need to be seeded.")
        else:
            visible = [
                item for item in rewards
                if partner_filter == "All apps" or item.get("partnerName") == partner_filter
            ]
            for reward in visible:
                cost = float(reward.get("creditsRequired") or 0)
                affordable = balance is not None and balance >= cost
                partner = reward.get("partnerName") or "Pharmacy app"
                artwork = partners.get(partner)
                with st.container(border=True):
                    if artwork:
                        image_col, details_col = st.columns([1.05, 2.95], gap="large", vertical_alignment="center")
                        with image_col:
                            st.image(artwork["image"], caption=None, use_container_width=True)
                        with details_col:
                            st.markdown(f"### {reward.get('title', 'Demo coupon')}")
                            st.markdown(f'<div class="mc-shop-partner">{partner}</div>', unsafe_allow_html=True)
                            st.caption(artwork["subtitle"])
                    else:
                        st.markdown(f"### {reward.get('title', 'Demo coupon')}")
                        st.caption(partner)
                    cost_col, redeem_col = st.columns([1, 2], vertical_alignment="center")
                    with cost_col:
                        st.metric("Coupon cost", f"{cost:,.0f} MC")
                    with redeem_col:
                        st.write(reward.get("description") or "Simulated demo coupon.")
                        if balance is not None and not affordable:
                            st.caption(f"You need {cost - balance:,.0f} more MediCredits.")
                        if st.button(
                            "Redeem coupon",
                            key=f"shop_redeem_{reward.get('rewardId')}",
                            disabled=not affordable,
                            type="primary" if affordable else "secondary",
                            use_container_width=True,
                        ):
                            result = api(
                                "POST",
                                "/api/reward-redemptions",
                                data={"rewardId": reward.get("rewardId")},
                            )
                            if result:
                                redemption = result.get("redemption", {})
                                st.session_state["shop_redeem_notice"] = (
                                    f"Demo coupon issued: {redemption.get('redemptionCode', '—')} · "
                                    f"{result.get('remainingBalance', '—')} MediCredits remaining."
                                )
                                st.rerun()

    with coupons_tab:
        if issued:
            for coupon in issued:
                with st.container(border=True):
                    partner = coupon.get("partnerName") or "Pharmacy app"
                    artwork = partners.get(partner)
                    image_col, details_col = st.columns([1, 3], gap="large", vertical_alignment="center")
                    with image_col:
                        if artwork:
                            st.image(artwork["image"], use_container_width=True)
                    with details_col:
                        st.markdown(f"### {coupon.get('title', 'Demo coupon')}")
                        st.caption(f"{partner} · {coupon.get('status', 'ISSUED')}")
                        st.code(coupon.get("redemptionCode", ""), language=None)
                        st.caption(
                            f"Redeemed for {float(coupon.get('creditsUsed') or 0):,.0f} MediCredits"
                        )
                        st.caption("Internal demo code only — not accepted by the pharmacy app.")
        else:
            st.info("Your redeemed coupons will appear here.")

    notice = st.session_state.pop("shop_redeem_notice", None)
    if notice:
        st.success(notice)


def customer_profile():
    st.title('Profile & addresses')
    st.caption('Your personal details and saved collection addresses.')

    profile = api('GET', '/api/users/me') or {}
    addresses = api('GET', '/api/users/me/addresses') or []
    st.session_state.setdefault('profile_editor_open', False)
    st.session_state.setdefault('address_editor_id', None)
    st.session_state.setdefault('avatar_style', 'Male')

    # Profile card: the avatar is a presentation choice only. Gender is not
    # currently collected or stored in the MediCycle user schema.
    with st.container(border=True):
        avatar_col, details_col = st.columns([1, 5], vertical_alignment='center')
        with avatar_col:
            avatar = '👨🏻' if st.session_state.avatar_style == 'Male' else '👩🏻'
            st.markdown(
                f'<div style="width:88px;height:88px;border-radius:26px;display:grid;place-items:center;'
                f'font-size:48px;background:linear-gradient(145deg,#e4f5ed,#ccebdd);'
                f'box-shadow:0 8px 22px rgba(20,90,70,.10)">{avatar}</div>',
                unsafe_allow_html=True,
            )
        with details_col:
            st.markdown('<div class="mc-section-label">ACCOUNT PROFILE</div>', unsafe_allow_html=True)
            st.markdown(f"### {profile.get('fullName') or 'Your name'}")
            st.write(profile.get('email') or 'Email not added')
            st.caption(profile.get('phone') or 'Phone number not added')
        avatar_col, action_col = st.columns([3, 2])
        with avatar_col:
            st.selectbox('Profile illustration', ['Male', 'Female'], key='avatar_style',
                         format_func=lambda value: 'Male avatar' if value == 'Male' else 'Female avatar')
        with action_col:
            st.write('')
            if st.button('Edit profile  →', key='open_profile_editor', use_container_width=True):
                st.session_state.profile_editor_open = not st.session_state.profile_editor_open
                st.rerun()

    if st.session_state.profile_editor_open:
        with st.container(border=True):
            st.subheader('Update profile')
            with st.form('profile_update'):
                name = st.text_input('Full name', value=profile.get('fullName') or '')
                email = st.text_input('Email', value=profile.get('email') or '')
                phone = st.text_input('Phone', value=profile.get('phone') or '')
                save_col, cancel_col = st.columns(2)
                with save_col:
                    save = st.form_submit_button('Save changes', type='primary', use_container_width=True)
                with cancel_col:
                    cancel = st.form_submit_button('Cancel', use_container_width=True)
            if save:
                result = api('PATCH', '/api/users/me', data={
                    'fullName': name.strip(), 'email': email.strip() or None, 'phone': phone.strip() or None
                })
                if result:
                    st.session_state.profile_editor_open = False
                    st.success('Profile updated successfully.')
                    st.rerun()
            if cancel:
                st.session_state.profile_editor_open = False
                st.rerun()

    st.divider()
    heading_col, add_col = st.columns([3, 1], vertical_alignment='center')
    with heading_col:
        st.subheader('Saved addresses')
        st.caption('Choose an address to edit it or add another collection location.')
    with add_col:
        if st.button('+ Add address', key='open_new_address', type='primary', use_container_width=True):
            st.session_state.address_editor_id = 'new'
            st.rerun()

    if addresses:
        for index, address in enumerate(addresses):
            label = address.get('addressLabel') or ('Home' if index == 0 else f'Address {index + 1}')
            with st.container(border=True):
                top_col, badge_col = st.columns([4, 1], vertical_alignment='center')
                with top_col:
                    st.markdown(f"**📍 {label}**")
                    st.write(address.get('addressLine') or '')
                    locality = ', '.join(part for part in [
                        address.get('city'), address.get('state')
                    ] if part)
                    st.caption(f"{locality} – {address.get('postalCode') or ''}")
                    if address.get('landmark'):
                        st.caption(f"Landmark: {address.get('landmark')}")
                with badge_col:
                    if address.get('isDefault'):
                        st.success('Default')
                if st.button('View / update address  →', key=f"edit_address_{address.get('addressId')}",
                             use_container_width=True):
                    st.session_state.address_editor_id = str(address.get('addressId'))
                    st.rerun()
    else:
        with st.container(border=True):
            st.info('No saved addresses yet. Add an address for doorstep medicine collection.')

    selected_address = next(
        (item for item in addresses if str(item.get('addressId')) == st.session_state.address_editor_id),
        None,
    )
    if st.session_state.address_editor_id == 'new' or selected_address:
        editing = selected_address or {}
        is_new = st.session_state.address_editor_id == 'new'
        with st.container(border=True):
            st.subheader('Add a new address' if is_new else 'Update saved address')
            with st.form('address_editor_form'):
                address_label = st.text_input('Address label', value=editing.get('addressLabel') or '', placeholder='Home, Work, etc.')
                address_line = st.text_input('Address line', value=editing.get('addressLine') or '')
                city = st.text_input('City', value=editing.get('city') or '')
                state = st.text_input('State', value=editing.get('state') or '')
                postal = st.text_input('Postal code', value=editing.get('postalCode') or '')
                landmark = st.text_input('Landmark (optional)', value=editing.get('landmark') or '')
                default = st.checkbox('Set as default address', value=bool(editing.get('isDefault')))
                save_col, cancel_col = st.columns(2)
                with save_col:
                    save_address = st.form_submit_button('Save address', type='primary', use_container_width=True)
                with cancel_col:
                    cancel_address = st.form_submit_button('Cancel', use_container_width=True)
            if save_address:
                payload = {
                    'addressLabel': address_label.strip() or None,
                    'addressLine': address_line.strip(), 'city': city.strip(),
                    'state': state.strip(), 'postalCode': postal.strip(),
                    'landmark': landmark.strip() or None,
                    'isDefault': default,
                    'latitude': editing.get('latitude'), 'longitude': editing.get('longitude'),
                }
                if is_new:
                    result = api('POST', '/api/users/me/addresses', data=payload)
                else:
                    result = api('PATCH', f"/api/users/me/addresses/{st.session_state.address_editor_id}", data=payload)
                if result:
                    st.session_state.address_editor_id = None
                    st.success('Address added.' if is_new else 'Address updated.')
                    st.rerun()
            if cancel_address:
                st.session_state.address_editor_id = None
                st.rerun()


def staff_workspace():
    st.title('Facility operations')
    memberships = api('GET', '/api/staff/me') or []
    if not memberships:
        st.warning('This account has no active facility-staff membership.')
        return
    facilities = {m['facility']['facilityName']: m['facility']['facilityId'] for m in memberships if m.get('facility')}
    facility_name = st.selectbox('Facility', list(facilities))
    facility_id = facilities[facility_name]
    dashboard = api('GET', '/api/staff/dashboard')
    if dashboard: st.json(dashboard)
    t_queue, t_intake, t_bins, t_logistics = st.tabs(['Return queue & inspection', 'Receive return', 'Storage bins', 'Logistics & disposal'])
    with t_queue:
        queue = api('GET', '/api/staff/returns') or []
        records_table(queue)
        if queue:
            rmap = {f"{r.get('returnId')} — {r.get('status')}": r.get('returnId') for r in queue}
            selected = st.selectbox('Select return to inspect', list(rmap))
            rid = rmap[selected]
            detail = api('GET', f'/api/staff/returns/{rid}')
            if detail:
                st.json(detail)
                items = detail.get('items', []) if isinstance(detail, dict) else []
                if items:
                    decision = st.radio('Whole-request decision', ['ACCEPTED', 'REJECTED'], horizontal=True, key='decision')
                    reason = st.text_input('Rejection reason (required for rejection)')
                    inspections = []
                    credits = {}
                    for item in items:
                        iid = item.get('returnItemId')
                        st.write(f"Item {iid} · quantity {item.get('quantity')}")
                        status = st.selectbox(f'Inspection {iid}', ['ACCEPTED', 'REJECTED'], key=f'inspect_{iid}')
                        inspections.append({'returnItemId': iid, 'inspectionStatus': status})
                        credits[str(iid)] = float(st.number_input(f'Credits for {iid}', min_value=0.0, value=0.0, key=f'credits_{iid}'))
                    if st.button('Submit request-wide inspection decision', type='primary'):
                        if decision == 'ACCEPTED' and any(x['inspectionStatus'] != 'ACCEPTED' for x in inspections):
                            st.error('Every item must be accepted for an accepted request.')
                        elif decision == 'REJECTED' and any(x['inspectionStatus'] != 'REJECTED' for x in inspections):
                            st.error('Every item must be rejected for a rejected request.')
                        else:
                            payload = {'decision': decision, 'rejectionReason': reason or None, 'itemInspections': inspections, 'creditsByItem': credits if decision == 'ACCEPTED' else {}}
                            result = api('POST', f'/api/staff/returns/{rid}/decision', data=payload)
                            if result: st.success('Decision recorded.'); st.json(result)
    with t_intake:
        queue = api('GET', '/api/staff/returns') or []
        if queue:
            rmap = {f"{r.get('returnId')} — {r.get('status')}": r.get('returnId') for r in queue}
            selected = st.selectbox('Return to receive', list(rmap), key='intake_return')
            with st.form('intake_form'):
                declared = st.number_input('Declared quantity', min_value=0, value=1)
                received = st.number_input('Received quantity', min_value=0, value=1)
                notes = st.text_area('Intake notes')
                submit = st.form_submit_button('Confirm physical receipt')
            if submit:
                result = api('POST', f"/api/staff/returns/{rmap[selected]}/intake", data={'facilityId': facility_id, 'declaredQuantity': declared, 'receivedQuantity': received, 'intakeNotes': notes or None})
                if result: st.success('Physical receipt recorded.')
        else: st.info('No returns in the queue.')
    with t_bins:
        bins = api('GET', '/api/staff/bins') or []
        records_table(bins, 'Storage bins')
        with st.form('bin_form'):
            code = st.text_input('Bin code')
            category = st.text_input('Storage category')
            capacity = st.number_input('Capacity units', min_value=1, value=100)
            create = st.form_submit_button('Create storage bin')
        if create:
            result = api('POST', '/api/staff/bins', data={'facilityId': facility_id, 'binCode': code, 'storageCategory': category, 'capacityUnits': int(capacity), 'binStatus': 'ACTIVE'})
            if result: st.success('Bin created.')
    with t_logistics:
        st.subheader('Assign a driver to a return')
        assignable_returns = api('GET', '/api/staff/returns') or []
        drivers = api('GET', '/api/staff/drivers') or []
        vehicles = api('GET', '/api/staff/vehicles') or []
        if assignable_returns and drivers:
            return_options = {f"{r.get('returnId')} — {r.get('status')}": r.get('returnId') for r in assignable_returns if r.get('returnMethod') == 'DOORSTEP_PICKUP'}
            driver_options = {f"{d.get('fullName')} — {d.get('driverId')}": d.get('driverId') for d in drivers}
            vehicle_options = {'No vehicle selected': None, **{f"{v.get('registrationNumber')} — {v.get('vehicleId')}": v.get('vehicleId') for v in vehicles}}
            if return_options:
                with st.form('assignment_form'):
                    selected_return = st.selectbox('Doorstep return', list(return_options))
                    selected_driver = st.selectbox('Available verified driver', list(driver_options))
                    selected_vehicle = st.selectbox('Vehicle', list(vehicle_options))
                    assign = st.form_submit_button('Create pickup assignment')
                if assign:
                    result = api('POST', '/api/staff/assignments', data={'returnId': return_options[selected_return], 'driverId': driver_options[selected_driver], 'vehicleId': vehicle_options[selected_vehicle]})
                    if result: st.success('Driver assigned.'); st.json(result)
            else:
                st.info('No doorstep returns are currently available for assignment.')
        else:
            st.info('Verified available drivers and doorstep returns are required before assignment.')
        st.subheader('Create pickup slot')
        with st.form('pickup_slot_form'):
            slot_day = st.date_input('Slot date')
            start_time = st.time_input('Start time')
            end_time = st.time_input('End time')
            slot_capacity = st.number_input('Capacity', min_value=1, value=5)
            create_slot = st.form_submit_button('Create pickup slot')
        if create_slot:
            payload = {'facilityId': facility_id, 'slotDate': datetime.combine(slot_day, start_time).isoformat(), 'startTime': datetime.combine(slot_day, start_time).isoformat(), 'endTime': datetime.combine(slot_day, end_time).isoformat(), 'capacity': int(slot_capacity)}
            result = api('POST', '/api/staff/pickup-slots', data=payload)
            if result: st.success('Pickup slot created.')
        for endpoint, label in [('/api/staff/commissions', 'Commissions'), ('/api/staff/commission-payouts', 'Commission payouts'), ('/api/staff/manifests', 'Collection manifests'), ('/api/staff/disposal-records', 'Disposal records')]:
            records_table(api('GET', endpoint) or [], label)
        st.subheader('Record disposal')
        with st.form('disposal_form'):
            category = st.text_input('Medicine category')
            quantity = st.number_input('Quantity disposed', min_value=0.01, value=1.0)
            method = st.text_input('Disposal method')
            submit = st.form_submit_button('Create disposal record')
        if submit:
            result = api('POST', '/api/staff/disposal-records', data={'facilityId': facility_id, 'medicineCategory': category, 'quantity': quantity, 'disposalMethod': method})
            if result: st.success('Disposal record created.')


def driver_workspace():
    st.title('Driver workspace')
    profile = api('GET', '/api/driver/me')
    if not profile:
        st.warning('This account is not linked to an active driver profile.')
        return
    st.json(profile)
    assignments = api('GET', '/api/driver/assignments') or []
    records_table(assignments, 'My pickup assignments')
    if assignments:
        amap = {f"{a.get('assignmentId')} — {a.get('status')}": a.get('assignmentId') for a in assignments}
        selected = st.selectbox('Update assignment', list(amap))
        new_status = st.selectbox('New status', ['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'PICKED_UP'])
        if st.button('Update pickup status'):
            result = api('POST', f"/api/driver/assignments/{amap[selected]}/status", data={'status': new_status})
            if result: st.success('Assignment updated.')
        st.subheader('Submit location update')
        with st.form('gps_form'):
            lat = st.number_input('Latitude', min_value=-90.0, max_value=90.0, value=0.0, format='%.6f')
            lon = st.number_input('Longitude', min_value=-180.0, max_value=180.0, value=0.0, format='%.6f')
            gps_status = st.text_input('Tracking status', value='IN_TRANSIT')
            send = st.form_submit_button('Send location')
        if send:
            result = api('POST', '/api/driver/tracking', data={'latitude': lat, 'longitude': lon, 'trackingStatus': gps_status})
            if result: st.success('Location update submitted.')


WORKSPACE_COOKIE_NAME = "medicycle_active_workspace"
WORKSPACE_COOKIE_DAYS = 365

CUSTOMER_PAGES = [
    "Dashboard", "My Medicines", "Medicine Apps", "Returns",
    "Wallet & rewards", "Shop", "Profile & addresses", "Certificates", "Notifications",
]
WORKSPACE_PAGES = {
    "Customer": CUSTOMER_PAGES,
    "Driver": ["Operations"],
    "Facility": ["Operations"],
}
WORKSPACE_DESCRIPTIONS = {
    "Customer": "Manage medicines, returns, collection addresses and MediCredits.",
    "Driver": "Manage assigned pickups, collection status and location updates.",
    "Facility": "Receive returns, inspect medicines, manage storage and disposal.",
}


def discover_workspaces() -> list[str]:
    """Discover operational memberships without showing expected 403 responses to other roles.

    Customer is the base account workspace in the current schema. Driver and facility
    access are derived from the existing Driver and FacilityStaff relationships.
    """
    available = ["Customer"]
    driver_profile = api("GET", "/api/driver/me", quiet=True)
    if driver_profile:
        available.append("Driver")
    staff_memberships = api("GET", "/api/staff/me", quiet=True)
    if staff_memberships:
        available.append("Facility")
    return available


def persist_workspace_preference(cookie_manager, workspace: str) -> None:
    """Persist only the workspace preference; authorization is rechecked on every run."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=WORKSPACE_COOKIE_DAYS)
    cookie_manager.set(
        WORKSPACE_COOKIE_NAME,
        workspace,
        key="medicycle_set_workspace",
        path="/",
        expires_at=expires_at,
        max_age=WORKSPACE_COOKIE_DAYS * 24 * 60 * 60,
        secure=True,
        same_site="strict",
    )


def workspace_settings(available_workspaces: list[str], active_workspace: str, cookie_manager) -> None:
    st.title("Settings")
    st.caption("Manage your MediCycle workspace preferences.")
    with st.container(border=True):
        st.subheader("Workspace")
        st.write(f"Current workspace: **{active_workspace}**")
        st.caption("Each workspace has its own navigation and operational tasks.")
        if len(available_workspaces) == 1:
            st.info("Only the Customer Workspace is currently linked to this account. Driver and Facility workspaces appear after an administrator links the relevant operational profile.")
            return
        selected_workspace = st.selectbox(
            "Switch workspace",
            available_workspaces,
            index=available_workspaces.index(active_workspace),
            key="settings_workspace_choice",
        )
        if st.button("Switch workspace", type="primary", use_container_width=True):
            if selected_workspace != active_workspace:
                st.session_state["active_workspace"] = selected_workspace
                persist_workspace_preference(cookie_manager, selected_workspace)
                st.rerun()
            else:
                st.success(f"{selected_workspace} Workspace is already active.")




def customer_notifications():
    """Render customer notifications as a readable activity feed."""
    st.subheader("Notifications")
    notifications = api("GET", "/api/notifications") or []
    if not notifications:
        st.info("You're all caught up. No notifications yet.")
        return

    unread_count = sum(1 for item in notifications if not item.get("isRead"))
    st.caption(f"{unread_count} unread · {len(notifications)} total")

    for item in notifications:
        title = item.get("title") or "MediCycle update"
        message = item.get("message") or "You have a new update."
        created = item.get("createdAt")
        timestamp = str(created).replace("T", " ")[:16] if created else "Date unavailable"
        is_read = bool(item.get("isRead"))
        with st.container(border=True):
            top_left, top_right = st.columns([5, 1])
            top_left.markdown(f"**{title}**")
            if not is_read:
                top_right.markdown("<span style='color:#2563eb;font-weight:600'>● UNREAD</span>", unsafe_allow_html=True)
            top_left.write(message)
            top_left.caption(timestamp)
            if not is_read and item.get("notificationId"):
                if st.button("Mark as read", key=f"read_notification_{item['notificationId']}"):
                    result = api("PATCH", f"/api/notifications/{item['notificationId']}/read")
                    if result:
                        st.rerun()


def main():
    # Restore authentication and workspace preference from separate cookies.
    cookie_manager = stx.CookieManager(key="medicycle_auth_cookie_manager")
    if st.session_state.pop("_clear_auth_cookie", False):
        if AUTH_COOKIE_NAME in (cookie_manager.cookies or {}):
            cookie_manager.delete(AUTH_COOKIE_NAME, key="medicycle_delete_auth")

    if not st.session_state.get("token"):
        saved_token = (cookie_manager.cookies or {}).get(AUTH_COOKIE_NAME)
        if saved_token:
            st.session_state["token"] = saved_token
            profile = api("GET", "/api/users/me")
            if profile:
                st.session_state["user"] = profile

    if not st.session_state.get("token"):
        notice = st.session_state.pop("session_notice", None)
        if notice:
            st.warning(notice)
        login_screen(cookie_manager)
        return

    user = st.session_state.get("user") or {}
    available_workspaces = discover_workspaces()

    # A saved preference never grants access: stale or unauthorised choices fall
    # back to Customer after live role discovery.
    saved_workspace = (cookie_manager.cookies or {}).get(WORKSPACE_COOKIE_NAME)
    if "active_workspace" not in st.session_state:
        st.session_state["active_workspace"] = (
            saved_workspace if saved_workspace in available_workspaces else "Customer"
        )
    if st.session_state["active_workspace"] not in available_workspaces:
        st.session_state["active_workspace"] = "Customer"
        persist_workspace_preference(cookie_manager, "Customer")

    active_workspace = st.session_state["active_workspace"]
    navigation = [*WORKSPACE_PAGES[active_workspace], "Settings"]

    with st.sidebar:
        st.markdown(
            '<div class="mc-brand"><div class="mc-mark" style="width:38px;height:38px;font-size:20px;border-radius:12px">♻</div>'
            '<strong style="font-family:Manrope,sans-serif;font-size:1.25rem;color:#143b35">MediCycle</strong></div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Signed in as {user.get('fullName', 'User')}")
        st.divider()
        st.markdown("**" + active_workspace + " Workspace**")
        page = st.radio(
            "Navigation",
            navigation,
            key=f"navigation_{active_workspace.lower()}",
            label_visibility="collapsed",
        )
        st.divider()
        st.caption(f"API: {API_BASE}")
        if st.button("Sign out", use_container_width=True):
            if AUTH_COOKIE_NAME in (cookie_manager.cookies or {}):
                cookie_manager.delete(AUTH_COOKIE_NAME, key="medicycle_logout_auth")
            if WORKSPACE_COOKIE_NAME in (cookie_manager.cookies or {}):
                cookie_manager.delete(WORKSPACE_COOKIE_NAME, key="medicycle_logout_workspace")
            st.session_state.clear()
            refresh()

    if page == "Settings":
        workspace_settings(available_workspaces, active_workspace, cookie_manager)
        return

    st.markdown(
        '<div class="mc-page-intro"><div><small>' + active_workspace.upper() + ' WORKSPACE</small>'
        '<strong>Care, collected responsibly.</strong>'
        '<span>' + WORKSPACE_DESCRIPTIONS[active_workspace] + '</span></div>'
        '<span>♻ &nbsp; Responsible returns</span></div>',
        unsafe_allow_html=True,
    )

    if active_workspace == "Customer":
        if page == "Dashboard":
            customer_dashboard()
        elif page == "My Medicines":
            customer_my_medicines()
        elif page == "Medicine Apps":
            customer_medicine_apps()
        elif page == "Returns":
            customer_returns()
        elif page == "Wallet & rewards":
            customer_wallet()
        elif page == "Shop":
            customer_shop()
        elif page == "Profile & addresses":
            customer_profile()
        elif page == "Certificates":
            records_table(api("GET", "/api/certificates") or [], "Disposal certificates")
        elif page == "Notifications":
            customer_notifications()
    elif active_workspace == "Driver":
        driver_workspace()
    elif active_workspace == "Facility":
        staff_workspace()


if __name__ == '__main__':
    main()
