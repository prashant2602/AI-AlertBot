"""
AlertBot — AI-Powered Project Alert Chatbot
Streamlit Web UI Entry Point
Run with: streamlit run app.py
"""

import os
import sys
import streamlit as st
from dotenv import load_dotenv

# ── Path setup so modules resolve correctly ───────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from database import init_db, seed_db, DB_PATH
from auth import authenticate, AuthUser
from chatbot import chat, get_greeting

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AlertBot",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Chat bubbles */
.user-bubble {
    background: #1a73e8;
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 10px 16px;
    margin: 4px 0;
    max-width: 80%;
    margin-left: auto;
    word-wrap: break-word;
}
.bot-bubble {
    background: #f1f3f4;
    color: #1a1a1a;
    border-radius: 18px 18px 18px 4px;
    padding: 10px 16px;
    margin: 4px 0;
    max-width: 90%;
    word-wrap: break-word;
}
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px;
}
/* Severity badges */
.badge-critical { background:#dc2626; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; font-weight:bold; }
.badge-high     { background:#ea580c; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; font-weight:bold; }
.badge-medium   { background:#d97706; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; font-weight:bold; }
.badge-low      { background:#2563eb; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; font-weight:bold; }
.badge-info     { background:#6b7280; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; font-weight:bold; }
/* Role chip */
.role-admin { background:#7c3aed; color:white; padding:3px 10px; border-radius:999px; font-size:0.78em; font-weight:600; }
.role-pm    { background:#0891b2; color:white; padding:3px 10px; border-radius:999px; font-size:0.78em; font-weight:600; }
/* Input area */
div[data-testid="stTextInput"] input { border-radius: 24px !important; }
/* Sidebar */
section[data-testid="stSidebar"] { background: #0f172a; }
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stButton button { background: #1e293b; border: 1px solid #334155; border-radius: 8px; color: #e2e8f0 !important; width: 100%; }
section[data-testid="stSidebar"] .stButton button:hover { background: #334155; }
</style>
""", unsafe_allow_html=True)


# ── DB Bootstrap ──────────────────────────────────────────────────────────────
@st.cache_resource
def bootstrap_database():
    """Initialize and seed the DB exactly once per server run."""
    try:
        init_db()
        # Only seed if users table is empty (first run)
        from database import get_connection
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        if count == 0:
            seed_db()
    except Exception as e:
        st.error(f"Database initialization failed: {e}")
    return True


bootstrap_database()


# ── Session state helpers ─────────────────────────────────────────────────────
def get_state(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def reset_session():
    for key in ["user", "chat_history", "display_messages", "login_error"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


# ── Login Screen ──────────────────────────────────────────────────────────────
def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🚨 AlertBot")
        st.markdown("##### AI-Powered Project Alert Management")
        st.divider()

        with st.form("login_form", clear_on_submit=False):
            st.markdown("**Sign in to your account**")
            username = st.text_input("Username", placeholder="e.g. carol_pm")
            password = st.text_input("Password", type="password", placeholder="Password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                user = authenticate(username.strip(), password)
                if user:
                    st.session_state["user"] = user
                    st.session_state["chat_history"] = []
                    st.session_state["display_messages"] = []
                    greeting = get_greeting(user)
                    st.session_state["display_messages"].append(
                        {"role": "assistant", "content": greeting}
                    )
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password.")

        if get_state("login_error"):
            st.error(st.session_state["login_error"])

        # Demo credentials hint
        with st.expander("💡 Demo Credentials"):
            st.markdown("""
| Username | Password | Role |
|----------|----------|------|
| `alice_admin` | `admin123` | Admin (all projects) |
| `bob_admin` | `admin456` | Admin (all projects) |
| `carol_pm` | `carol123` | PM → Alpha Portal, Beta Analytics |
| `david_pm` | `david123` | PM → Gamma Migration, Delta Security |
| `eve_pm` | `eve123` | PM → Epsilon ML, Zeta Mobile |
| `frank_pm` | `frank123` | PM → Zeta Mobile |
""")


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(user: AuthUser):
    with st.sidebar:
        st.markdown("## 🚨 AlertBot")
        st.divider()

        # User info
        role_badge = (
            '<span class="role-admin">ADMIN</span>'
            if user.is_admin
            else '<span class="role-pm">PM</span>'
        )
        st.markdown(
            f"**{user.full_name}** {role_badge}<br>"
            f"<small style='opacity:0.7'>{user.email}</small>",
            unsafe_allow_html=True,
        )
        st.divider()

        # Accessible projects
        st.markdown("**📁 Your Projects**")
        if user.is_admin:
            st.markdown("*All projects (Admin)*")
        else:
            for pname in user.project_names:
                st.markdown(f"• {pname}")

        st.divider()

        # Quick-fire query shortcuts
        st.markdown("**⚡ Quick Queries**")
        quick_queries = [
            ("🔴 Critical Alerts", "Show me all critical open alerts"),
            ("🔒 Security Issues", "What are the open security alerts?"),
            ("📊 Project Summary", "Give me a summary of alerts by project"),
            ("💰 Budget Alerts", "Are there any budget-related alerts?"),
            ("📅 Today's Alerts", "Show alerts from today"),
            ("✅ Resolved Today", "Show alerts resolved today"),
        ]
        for label, query in quick_queries:
            if st.button(label, key=f"quick_{label}"):
                st.session_state["pending_query"] = query

        st.divider()

        # Clear chat
        if st.button("🗑️ Clear Chat"):
            greeting = get_greeting(user)
            st.session_state["chat_history"] = []
            st.session_state["display_messages"] = [
                {"role": "assistant", "content": greeting}
            ]
            st.rerun()

        # Logout
        if st.button("🚪 Sign Out"):
            reset_session()


# ── Chat area ─────────────────────────────────────────────────────────────────
def render_chat(user: AuthUser):
    st.markdown(f"### 💬 Chat — Logged in as **{user.full_name}**")

    display_messages = get_state("display_messages", [])

    # Render message history
    chat_area = st.container()
    with chat_area:
        for msg in display_messages:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🚨"):
                    st.markdown(msg["content"])

    # Handle pending quick-query from sidebar buttons
    pending = st.session_state.pop("pending_query", None)

    # Chat input
    user_input = st.chat_input("Ask about your project alerts…")

    # Use pending query OR typed input
    query = pending or user_input

    if query:
        # Show user message immediately
        st.session_state["display_messages"].append({"role": "user", "content": query})

        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant", avatar="🚨"):
            with st.spinner("Thinking…"):
                try:
                    reply, updated_history = chat(
                        user=user,
                        user_message=query,
                        conversation_history=st.session_state.get("chat_history", []),
                    )
                    st.session_state["chat_history"] = updated_history
                    st.session_state["display_messages"].append(
                        {"role": "assistant", "content": reply}
                    )
                    st.markdown(reply)
                except EnvironmentError as e:
                    err = f"⚠️ **Configuration error:** {e}"
                    st.error(err)
                    st.session_state["display_messages"].append(
                        {"role": "assistant", "content": err}
                    )
                except Exception as e:
                    err = f"⚠️ **Error:** {e}"
                    st.error(err)
                    st.session_state["display_messages"].append(
                        {"role": "assistant", "content": err}
                    )


# ── Main entry ────────────────────────────────────────────────────────────────
def main():
    user: AuthUser | None = st.session_state.get("user")

    if user is None:
        render_login()
    else:
        render_sidebar(user)
        render_chat(user)


if __name__ == "__main__":
    main()
