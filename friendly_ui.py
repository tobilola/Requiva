"""Requiva's original purple Supply Hub welcome and actionable onboarding."""
from pathlib import Path
from html import escape
import streamlit as st

TEAM_IMAGE = Path(__file__).with_name('requiva_lab_team.png')

CSS = """
<style>
:root{--rq-purple:#7135c8;--rq-ink:#211942;--rq-line:#e6dcf7}
.requiva-hero-copy{padding:1.35rem .25rem .6rem}
.requiva-hero-copy .eyebrow{font-size:.79rem;letter-spacing:.11em;font-weight:800;color:#743ec4;text-transform:uppercase}
.requiva-hero-copy h2{font-size:clamp(1.7rem,2.6vw,2.45rem)!important;line-height:1.12;margin:.3rem 0 .65rem;color:#211942!important;letter-spacing:-.035em}
.requiva-hero-copy h2 span{color:#803ecb}
.requiva-hero-copy p{font-size:1rem;color:#504869;line-height:1.55;margin:0}
.requiva-team-caption{font-size:.78rem;color:#645c7c;text-align:center}
.requiva-guide{border:1px solid #ddc9fb;border-radius:22px;padding:1.4rem 1.3rem 1.5rem;background:linear-gradient(130deg,#ffffff,#fbf7ff 72%,#f1e6ff);box-shadow:0 8px 26px rgba(80,42,139,.06);margin:1.1rem 0 1.3rem}
.requiva-guide-head{display:flex;align-items:baseline;gap:1.1rem;flex-wrap:wrap;margin-bottom:1.2rem}
.requiva-guide-head h3{font-size:1.5rem!important;color:#211942!important;margin:0;letter-spacing:-.02em}
.requiva-guide-head p{color:#64597d;margin:0;font-size:.92rem}
.requiva-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem}
.requiva-step{min-width:0;padding:.75rem .8rem .8rem;background:rgba(255,255,255,.74);border-radius:15px;animation:rq-in .55s ease both}
.requiva-step:nth-child(2){animation-delay:.08s}.requiva-step:nth-child(3){animation-delay:.16s}.requiva-step:nth-child(4){animation-delay:.24s}
.requiva-step-icon{width:55px;height:55px;border-radius:19px;background:#efe5ff;display:grid;place-items:center;font-size:1.7rem;margin-bottom:.75rem}
.requiva-step-num{display:inline-flex;background:#7439c5;color:white;font-size:.75rem;border-radius:50%;width:24px;height:24px;align-items:center;justify-content:center;font-weight:800;margin-bottom:.45rem}
.requiva-step strong{display:block;color:#211942;font-size:1rem;line-height:1.3}
.requiva-step p{color:#665d79;font-size:.85rem;line-height:1.45;margin:.3rem 0 0}
.requiva-section-label{font-size:1.22rem;font-weight:800;color:#211942;margin:.4rem 0 .25rem}
.requiva-action{border-radius:17px;border:1px solid #e3d6f5;padding:1rem 1.05rem;min-height:104px;margin:.4rem 0 .2rem;box-shadow:0 3px 14px rgba(80,42,139,.035)}
.requiva-action.mint{background:linear-gradient(125deg,#eafbf4,#f8fffc)}
.requiva-action.blue{background:linear-gradient(125deg,#e8f2ff,#f8fbff)}
.requiva-action.peach{background:linear-gradient(125deg,#fff3e5,#fffaf4)}
.requiva-action.lilac{background:linear-gradient(125deg,#f1e9ff,#fcfaff)}
.requiva-action h4{margin:.1rem 0 .3rem;font-size:1.02rem;color:#241a44;font-weight:800}
.requiva-action p{margin:0;font-size:.85rem;line-height:1.45;color:#605671}
.requiva-action .symbol{font-size:1.5rem}
.requiva-footnote{color:#776d89;font-size:.82rem;margin:1rem 0}
@keyframes rq-in{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:800px){.requiva-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:440px){.requiva-steps{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.requiva-step{animation:none}}
</style>
"""

STEPS = [
    ('📝', 'Request supplies', 'Share what your experiment needs.'),
    ('🔎', 'Admin review', 'Your lab checks and approves the request.'),
    ('🛒', 'Place the order', 'Purchase through ShopBlue or the Stockroom.'),
    ('📦', 'Receive & use', 'A designated receiver records deliveries.'),
]


def welcome(email):
    st.markdown(CSS, unsafe_allow_html=True)
    left, right = st.columns([1.15, 1], gap='large', vertical_alignment='center')
    with left:
        st.markdown('''<div class="requiva-hero-copy">
            <div class="eyebrow">A little less admin. A lot more science.</div>
            <h2>Welcome to the<br><span>Requiva Supply Hub</span> 🧪</h2>
            <p>One shared place for your lab's requests, orders, and deliveries. Made for the way real labs work together.</p>
            </div>''', unsafe_allow_html=True)
    with right:
        if TEAM_IMAGE.is_file():
            st.image(str(TEAM_IMAGE), use_container_width=True)
            st.markdown('<div class="requiva-team-caption">A lab works best when everyone is part of the team.</div>', unsafe_allow_html=True)

    steps = ''.join(
        f'<div class="requiva-step"><div class="requiva-step-num">{i}</div>'
        f'<div class="requiva-step-icon">{icon}</div>'
        f'<strong>{escape(title)}</strong><p>{escape(detail)}</p></div>'
        for i, (icon, title, detail) in enumerate(STEPS, 1)
    )
    st.markdown('''<div class="requiva-guide">
        <div class="requiva-guide-head"><h3>How Requiva works</h3>
        <p>From request to delivery — a clear process for your lab.</p></div>
        <div class="requiva-steps">''' + steps + '</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="requiva-section-label">What would you like to do?</div>', unsafe_allow_html=True)
    cols = st.columns(4, gap='small')
    actions = [
        ('mint', '🛒', 'New supply request', 'Tell your lab what you need.', 'rq_request'),
        ('blue', '📎', 'Upload requisition', 'For an approved order.', 'rq_upload'),
        ('peach', '👥', 'Shared requests', 'Check before requesting again.', 'rq_shared'),
        ('lilac', '📖', 'User handbook', 'See the complete step-by-step guide.', 'rq_handbook'),
    ]
    for col, (theme, icon, title, desc, key) in zip(cols, actions):
        with col:
            st.markdown(f'<div class="requiva-action {theme}"><div class="symbol">{icon}</div><h4>{escape(title)}</h4><p>{escape(desc)}</p></div>', unsafe_allow_html=True)
            if st.button('Open →', key=key, use_container_width=True):
                st.session_state['rq_selected_action'] = key
                if key == 'rq_request':
                    st.session_state['rq_expand_request'] = True
                if key == 'rq_handbook':
                    st.session_state['rq_expand_handbook'] = True
                st.rerun()
    chosen = st.session_state.get('rq_selected_action')
    if chosen == 'rq_request':
        st.info('Your request form is open below. Check the shared board first to avoid duplicates.')
    elif chosen == 'rq_upload':
        st.info('To upload a requisition, an admin selects an approved request under **Manage requests**, then confirms the purchase and attaches its PDF or image. Uploading does not place the purchase automatically.')
    elif chosen == 'rq_shared':
        st.info('The **Shared request board** is just below. It shows requests from your lab, so you can check for duplicates.')
    elif chosen == 'rq_handbook':
        st.info('The **How Requiva Works — Quick Handbook** is expanded below.')
    st.markdown('<div class="requiva-footnote">Built around lab teamwork • Every request has a clear next step • Financial reports stay in Overview</div>', unsafe_allow_html=True)
