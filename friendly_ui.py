"""Optional scientist avatars and a lightweight, accessible onboarding animation."""
from html import escape
import streamlit as st
from utils import db, USE_FIRESTORE

AVATARS = {"Female scientist": "👩‍🔬", "Male scientist": "👨‍🔬", "Neutral scientist": "🧑‍🔬"}
STEPS = [
    ("🧪", "1. Request supplies", "Check shared requests, then add what your experiment needs."),
    ("📋", "2. Admin reviews", "The admin approves or rejects your request."),
    ("🛒", "3. Order placed", "The admin purchases through ShopBlue or the Stockroom and uploads a requisition."),
    ("📦", "4. Package arrives", "A designated receiver confirms what arrived, including partial deliveries."),
]

def profile(email):
    """Read only the user's own profile; never change roles or lab membership."""
    defaults = {"display_name": email.split("@")[0], "avatar": "Neutral scientist"}
    if not USE_FIRESTORE or db is None:
        return defaults
    try:
        snap = db.collection("users").document(email.lower()).get()
        if snap.exists:
            data = snap.to_dict() or {}
            defaults["display_name"] = str(data.get("display_name") or defaults["display_name"])[:60]
            chosen = data.get("avatar")
            if chosen in AVATARS: defaults["avatar"] = chosen
    except Exception:
        pass
    return defaults

def profile_editor(email):
    p = profile(email)
    with st.expander("🎨 My scientist avatar", expanded=False):
        st.caption("Choose how you appear in Requiva. No ethnicity information is collected.")
        with st.form("scientist_profile_form"):
            name = st.text_input("Display name", value=p["display_name"], max_chars=60)
            choice = st.radio("My scientist avatar", list(AVATARS), index=list(AVATARS).index(p["avatar"]))
            st.markdown(f"### {AVATARS[choice]} {escape(name)}")
            save = st.form_submit_button("Save my avatar")
        if save:
            if not name.strip():
                st.error("Enter a display name.")
            elif not USE_FIRESTORE or db is None:
                st.warning("Profile saving requires Firestore.")
            else:
                try:
                    # Merge ensures password, lab, and role remain unchanged.
                    db.collection("users").document(email.lower()).set({"display_name": name.strip(), "avatar": choice}, merge=True)
                    st.success("Avatar saved! ✨")
                    st.rerun()
                except Exception as exc:
                    st.error("Unable to save your profile. Please try again.")

def welcome(email):
    p = profile(email)
    st.markdown("""<style>
    .requiva-hello {padding:1.15rem 1.4rem;border-radius:20px;background:linear-gradient(110deg,#e9f5ff,#f3eaff,#e6fff2);border:1px solid #d9dcff;color:#173052;margin-bottom:1rem}
    .requiva-hello h2 {color:#173052 !important;margin:0;font-size:1.55rem}
    .requiva-hello p {margin:.35rem 0 0;color:#344861}
    .requiva-step {background:#f8faff;border:1px solid #d9e5ff;border-radius:16px;padding:1rem;min-height:150px;animation:requiva-pop .65s ease both;color:#173052}
    .requiva-step strong {display:block;margin:.4rem 0}
    .requiva-step span {font-size:1.65rem}
    @keyframes requiva-pop {from {opacity:0;transform:translateY(8px)} to {opacity:1;transform:translateY(0)}}
    @media(prefers-reduced-motion:reduce){.requiva-step{animation:none}}
    </style>""", unsafe_allow_html=True)
    st.markdown(f'<div class="requiva-hello"><h2>{AVATARS[p["avatar"]]} Welcome to the lab, {escape(p["display_name"])}! 👋</h2><p>Great science starts with teamwork. Let’s keep our supplies organized together.</p></div>',unsafe_allow_html=True)
    with st.expander("🎬 Watch how Requiva works — 4 quick steps",expanded=True):
        st.caption("A simple, gently animated guide. All instructions are readable without animation.")
        cols=st.columns(4)
        for i,((emoji,title,detail),col) in enumerate(zip(STEPS,cols)):
            with col:
                st.markdown(f'<div class="requiva-step" style="animation-delay:{i*0.12}s"><span>{emoji}</span><strong>{escape(title)}</strong><div>{escape(detail)}</div></div>',unsafe_allow_html=True)
        st.caption("Tip: Check the Shared request board before submitting, to avoid duplicate orders. 💡")
