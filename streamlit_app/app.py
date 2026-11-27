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
st.write("Configured API:", API_BASE)

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
@media(max-width:900px){ .mc-auth-hero{min-height:300px;padding:28px;} .mc-auth-hero h2{font-size:1.65rem;} .mc-wordmark{font-size:1.7rem;} }
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


def api(method: str, path: str, *, data=None, params=None, auth=True):
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


def customer_dashboard():
    st.title('Customer dashboard')
    profile = api('GET', '/api/users/me')
    wallet = api('GET', '/api/wallet')
    returns = api('GET', '/api/returns')
    c1, c2, c3 = st.columns(3)
    c1.metric('MediCredits', wallet.get('availableBalance', '—') if wallet else '—')
    c2.metric('Return requests', len(returns) if isinstance(returns, list) else '—')
    c3.metric('Account', profile.get('accountStatus', '—') if profile else '—')
    st.markdown('#### Your recent returns')
    records_table(returns[:8] if isinstance(returns, list) else [])
    st.info('Credits are added only after the facility physically receives and verifies an entire return request.')


def customer_my_medicines():
    st.title("My Medicines")
    st.caption("Track medicines purchased from pharmacy apps. Add details from your order or medicine packaging.")
    st.info("Tata 1mg and PharmEasy are source labels only; MediCycle does not currently import live order history. Near-expiry means 30 days or less. Expired means the expiry date is before today.")
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
        st.subheader("Expired medicines ready for return")
        if bucket:
            st.warning("These expired medicines were added automatically. Review them before submitting a return.")
            records_table(bucket)
            addresses=api("GET","/api/users/me/addresses") or []
            facilities=api("GET","/api/facilities") or []
            slots=api("GET","/api/pickup-slots") or []
            with st.form("submit_expired_bucket"):
                method=st.radio("Return method",["DOORSTEP_PICKUP","PHARMACY_DROPOFF"],format_func=lambda x:"Doorstep pickup" if x=="DOORSTEP_PICKUP" else "Direct facility drop-off",horizontal=True)
                address_map={f"{x.get('addressLine')}, {x.get('city')}":x.get("addressId") for x in addresses}
                facility_map={f"{x.get('facilityName')} — {x.get('address')}":x.get("facilityId") for x in facilities}
                slot_map={f"{x.get('slotDate')} {x.get('startTime')}–{x.get('endTime')}":x.get("pickupSlotId") for x in slots if str(x.get("slotStatus","")).upper() in ("AVAILABLE","OPEN")}
                address_choice=st.selectbox("Pickup address",list(address_map)) if address_map else None
                facility_choice=st.selectbox("Drop-off facility",list(facility_map)) if method=="PHARMACY_DROPOFF" and facility_map else None
                slot_choice=st.selectbox("Pickup slot",list(slot_map)) if method=="DOORSTEP_PICKUP" and slot_map else None
                send=st.form_submit_button("Submit expired medicines as a return",type="primary")
            if send:
                if method=="DOORSTEP_PICKUP" and (not address_choice or not slot_choice): st.error("A saved address and available pickup slot are required.")
                elif method=="PHARMACY_DROPOFF" and not facility_choice: st.error("Select an operational drop-off facility.")
                else:
                    result=api("POST","/api/return-bucket/submit",data={"addressId":address_map.get(address_choice) if address_choice else None,"returnMethod":method,"pickupSlotId":slot_map.get(slot_choice) if slot_choice else None,"facilityId":facility_map.get(facility_choice) if facility_choice else None})
                    if result: st.success(f"Return request submitted with {result.get('submittedItems')} expired medicine entries."); st.rerun()
        else: st.success("Your Return Bucket is empty. Expired tracked medicines will appear here automatically.")


def customer_returns():
    st.title('Medicine returns')
    tab_new, tab_history = st.tabs(['Create return', 'Return history'])
    with tab_new:
        addresses = api('GET', '/api/users/me/addresses') or []
        facilities = api('GET', '/api/facilities') or []
        slots = api('GET', '/api/pickup-slots') or []
        medicine_catalogue = api('GET', '/api/medicines/catalogue', params={'limit': 100}) or []
        medicine_map = {
            f"{m.get('name')} {m.get('strength') or ''} — {m.get('dosageForm') or 'Medicine'}": m.get('medicineId')
            for m in medicine_catalogue
        }
        with st.form('return_form'):
            method = st.radio('Return method', ['DOORSTEP_PICKUP', 'PHARMACY_DROPOFF'], format_func=lambda x: 'Doorstep pickup' if x == 'DOORSTEP_PICKUP' else 'Direct facility drop-off', horizontal=True)
            address_map = {f"{a.get('addressLine')}, {a.get('city')} ({a.get('addressId')})": a.get('addressId') for a in addresses}
            facility_map = {f"{f.get('facilityName')} — {f.get('address')} ({f.get('facilityId')})": f.get('facilityId') for f in facilities}
            slot_map = {f"{s.get('slotDate')} {s.get('startTime')}–{s.get('endTime')} ({s.get('pickupSlotId')})": s.get('pickupSlotId') for s in slots if str(s.get('slotStatus', '')).upper() in ('AVAILABLE', 'OPEN')}
            address_choice = st.selectbox('Return address', list(address_map), disabled=not address_map) if address_map else None
            facility_choice = st.selectbox('Drop-off facility', list(facility_map), disabled=not facility_map) if method == 'PHARMACY_DROPOFF' and facility_map else None
            slot_choice = st.selectbox('Pickup slot', list(slot_map), disabled=not slot_map) if method == 'DOORSTEP_PICKUP' and slot_map else None
            st.markdown('**Medicines in this return request**')
            item_count = st.number_input('Number of different medicine entries', min_value=1, max_value=10, value=1, step=1)
            selected_items = []
            for index in range(int(item_count)):
                st.markdown(f'**Medicine entry {index + 1}**')
                medicine_choice = st.selectbox(
                    'Select medicine from catalogue',
                    ['Choose a medicine…', *medicine_map.keys()],
                    key=f'medicine_choice_{index}',
                    disabled=not medicine_map,
                    help='Start typing to search the catalogue.',
                )
                qty = st.number_input('Quantity', min_value=1, max_value=10000, value=1, key=f'medicine_qty_{index}')
                packaging = st.selectbox('Packaging condition', ['SEALED', 'INTACT', 'DAMAGED', 'OPENED', 'UNKNOWN'], key=f'medicine_packaging_{index}')
                selected_items.append({'medicineId': medicine_map.get(medicine_choice), 'quantity': int(qty), 'packagingCondition': packaging})
            notes = st.text_area('Additional notes (optional)')
            submit = st.form_submit_button('Submit return request', type='primary', use_container_width=True)
        if submit:
            if any(not item.get('medicineId') for item in selected_items):
                st.error('Search and select a medicine for every entry.')
            elif method == 'DOORSTEP_PICKUP' and (not address_choice or not slot_choice):
                st.error('A saved address and available pickup slot are required.')
            elif method == 'PHARMACY_DROPOFF' and not facility_choice:
                st.error('Select an operational drop-off facility.')
            else:
                payload = {
                    'addressId': address_map.get(address_choice) if address_choice else None,
                    'returnMethod': method,
                    'pickupSlotId': slot_map.get(slot_choice) if slot_choice else None,
                    'facilityId': facility_map.get(facility_choice) if facility_choice else None,
                    'requestNotes': notes or None,
                    'items': selected_items
                }
                result = api('POST', '/api/returns', data=payload)
                if result:
                    st.success('Return request submitted.')
                    st.json(result)
    with tab_history:
        history = api('GET', '/api/returns') or []
        records_table(history)
        if history:
            labels = {f"{r.get('returnId')} — {r.get('status')}": r.get('returnId') for r in history}
            selected = st.selectbox('Inspect a return', list(labels))
            detail = api('GET', f"/api/returns/{labels[selected]}")
            if detail:
                st.json(detail)


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

def customer_profile():
    st.title('Profile & addresses')
    profile = api('GET', '/api/users/me')
    if profile:
        with st.form('profile_update'):
            name = st.text_input('Full name', value=profile.get('fullName') or '')
            email = st.text_input('Email', value=profile.get('email') or '')
            phone = st.text_input('Phone', value=profile.get('phone') or '')
            save = st.form_submit_button('Save profile')
        if save:
            result = api('PATCH', '/api/users/me', data={'fullName': name, 'email': email or None, 'phone': phone or None})
            if result: st.success('Profile updated.')
    st.subheader('Saved addresses')
    addresses = api('GET', '/api/users/me/addresses') or []
    records_table(addresses)
    with st.form('new_address'):
        st.markdown('**Add address**')
        address_line = st.text_input('Address line')
        city = st.text_input('City')
        state = st.text_input('State')
        postal = st.text_input('Postal code')
        default = st.checkbox('Set as default')
        add = st.form_submit_button('Add address')
    if add:
        result = api('POST', '/api/users/me/addresses', data={'addressLine': address_line, 'city': city, 'state': state, 'postalCode': postal, 'isDefault': default})
        if result: st.success('Address added.')


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


def main():
    # Streamlit session_state is reset by a browser refresh. Restore the
    # short-lived API token from a browser cookie and rehydrate the user profile.
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

    if not st.session_state.get('token'):
        notice = st.session_state.pop('session_notice', None)
        if notice:
            st.warning(notice)
        login_screen(cookie_manager)
        return
    user = st.session_state.get('user') or {}
    with st.sidebar:
        st.markdown('<div class="mc-brand"><div class="mc-mark" style="width:38px;height:38px;font-size:20px;border-radius:12px">♻</div><strong style="font-family:Manrope,sans-serif;font-size:1.25rem;color:#143b35">MediCycle</strong></div>', unsafe_allow_html=True)
        st.caption(f"Signed in as {user.get('fullName', 'User')}")
        page = st.radio('Workspace', ['Dashboard', 'My Medicines', 'Returns', 'Wallet & rewards', 'Profile & addresses', 'Facility operations', 'Driver workspace', 'Certificates', 'Notifications'])
        if st.button('Sign out', use_container_width=True):
            if AUTH_COOKIE_NAME in (cookie_manager.cookies or {}):
                cookie_manager.delete(AUTH_COOKIE_NAME, key='medicycle_logout_auth')
            st.session_state.clear(); refresh()
        st.divider()
        st.caption(f'API: {API_BASE}')
    if page == 'Dashboard': customer_dashboard()
    elif page == 'My Medicines': customer_my_medicines()
    elif page == 'Returns': customer_returns()
    elif page == 'Wallet & rewards': customer_wallet()
    elif page == 'Profile & addresses': customer_profile()
    elif page == 'Facility operations': staff_workspace()
    elif page == 'Driver workspace': driver_workspace()
    elif page == 'Certificates': records_table(api('GET', '/api/certificates') or [], 'Disposal certificates')
    elif page == 'Notifications': records_table(api('GET', '/api/notifications') or [], 'Notifications')

if __name__ == '__main__':
    main()
