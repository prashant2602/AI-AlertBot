"""
AlertBot AI Chat Engine
Uses Groq (Llama 3.3) to interpret natural language queries, extract filter intent,
fetch relevant data from SQLite (via RBAC-aware query layer), and compose responses.
"""

import os
import json
from groq import Groq
from auth import AuthUser
from alerts import (
    get_alerts, get_alert_by_id, get_alert_summary, get_projects_for_user,
    get_project_assignments, get_alerts_by_manager,
    create_alert, assign_alert, add_alert_comment, get_alert_comments,
    update_alert_severity, delete_alert,
)

# ── Groq client (lazy, once per process) ──────────────────────────────────────
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. "
                "Please add it to your .env file or environment variables."
            )
        _client = Groq(api_key=api_key)
    return _client


_MODEL = "llama-3.3-70b-versatile"


# ── System prompt builder ─────────────────────────────────────────────────────

def _build_system_prompt(user: AuthUser, projects: list[dict]) -> str:
    role_desc = "an Administrator with access to ALL projects" if user.is_admin else (
        f"a Project Manager with access to: {', '.join(user.project_names) or 'no projects'}"
    )
    project_list = "\n".join(
        f"  - {p['name']} (status: {p['status']})" for p in projects
    ) or "  (none)"

    return f"""You are AlertBot, an intelligent assistant for managing project alerts in an enterprise project tracking system.

## Current User
- Name: {user.full_name}
- Username: {user.username}
- Role: {user.role.upper()} — {role_desc}

## Accessible Projects
{project_list}

## Your Capabilities
You can help the user with:
1. **Listing alerts** — by project, severity, status, category, or date range
2. **Summarizing alert status** — counts by severity, status, or project
3. **Filtering alerts** — "show me all critical alerts", "what's open in Alpha Portal?"
4. **Explaining alerts** — detail on a specific alert, its description, who raised it
5. **Trend questions** — "what are the most urgent issues?", "any security alerts?"
6. **Project assignments** — (admin only) "who manages Alpha Portal?", "which PM is assigned to each project?", "show me project-manager assignments"
7. **Manager alert stats** — (admin only) "which manager has the most alerts?", "who has the least open alerts?", "rank PMs by alert count"
8. **Create alert** — "Create a critical security alert for Alpha Portal titled SSL cert expiring"
9. **Assign alert** — "Assign alert #5 to carol_pm", "Assign this to david_pm"
10. **Add comment** — "Add comment to alert #3: vendor has been notified"
11. **View comments** — "Show comments on alert #7", "What notes are there on alert #12?"
12. **Update severity** — (admin only) "Change severity of alert #5 to critical", "Downgrade alert #12 to low"
13. **Delete alert** — "Delete alert #5", "Remove alert #12" (admins: any alert; PMs: only their project alerts)
14. **Check permissions** — "Can I add an alert?", "Am I allowed to delete alerts?", "What can I modify?", "Do I have permission to create alerts for Beta Analytics?"

## Important Rules
- You ONLY have access to data for the projects listed above. NEVER discuss or imply data from other projects.
- If asked about a project not in the user's accessible list, politely say it's outside their access scope.
- Always be concise, professional, and helpful.
- When presenting multiple alerts, organize by severity (critical → high → medium → low → info).
- Dates are in ISO format (YYYY-MM-DD HH:MM:SS). Display them in a human-friendly way.
- If the data set is empty, say so clearly and suggest alternatives.

## Severity Color Guide (for context in descriptions)
Critical  |  High  |  Medium  |  Low  |  Info

## Response Format
- Be conversational but structured.
- Use markdown tables or bullet lists when showing multiple alerts.
- Keep summaries tight — lead with the key insight, then details.
- Do not repeat the user's question back to them.
"""


# ── Intent extraction schema (OpenAI-compatible function calling) ─────────────

_INTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_alert_query_intent",
        "description": (
            "Extract structured query parameters from the user's natural language request "
            "about project alerts. Return null for any field not mentioned."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent_type": {
                    "type": "string",
                    "enum": ["list_alerts", "summary", "project_info", "project_assignments", "manager_alert_stats", "specific_alert", "create_alert", "assign_alert", "add_comment", "get_comments", "update_severity", "delete_alert", "check_permission", "general"],
                    "description": "Primary intent of the query."
                },
                "permission_action": {
                    "type": "string",
                    "enum": ["add", "delete", "modify", "all"],
                    "description": "Used with check_permission intent. The action the user is asking if they can perform: 'add' (create alert), 'delete' (delete alert), 'modify' (update/assign/comment on alert), or 'all' (general permissions overview)."
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name or partial name mentioned. Omit if not specified."
                },
                "severity": {
                    "type": "string",
                    "description": "Comma-separated severities: critical, high, medium, low, info. Omit if not specified."
                },
                "status": {
                    "type": "string",
                    "description": "Alert status: open, acknowledged, resolved, closed. Omit if not specified."
                },
                "category": {
                    "type": "string",
                    "description": "Alert category: performance, security, budget, schedule, quality, dependency, general."
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format. Omit if not specified."
                },
                "date_to": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format. Omit if not specified."
                },
                "alert_id": {
                    "type": "integer",
                    "description": "Specific alert ID if the user references one. Omit otherwise."
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of results. Default 20, max 50."
                },
                "new_alert_title": {
                    "type": "string",
                    "description": "Title for a new alert being created."
                },
                "new_alert_description": {
                    "type": "string",
                    "description": "Description/details for a new alert being created."
                },
                "assigned_to": {
                    "type": "string",
                    "description": "Username to assign the alert to (e.g. carol_pm, david_pm)."
                },
                "comment_text": {
                    "type": "string",
                    "description": "The comment text to add to an alert."
                }
            },
            "required": ["intent_type"]
        }
    }
}


def _extract_intent(user_message: str, conversation_history: list[dict]) -> dict:
    """Use Groq function calling to extract structured query intent from user message."""
    client = _get_client()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a query intent extractor for an alert management system. "
                "Today's date is 2026-04-24. "
                "Extract the user's alert query intent into structured parameters. "
                "For relative dates like 'today', 'this week', 'yesterday', compute actual YYYY-MM-DD values. "
                "When the user asks whether they can, are allowed to, or have permission to add/create, delete/remove, "
                "or modify/update/change/edit alerts, use intent_type='check_permission' and set permission_action "
                "to 'add', 'delete', or 'modify' accordingly. Use 'all' if the question is general (e.g. 'what can I do?')."
            )
        }
    ] + conversation_history[-6:] + [{"role": "user", "content": user_message}]

    response = client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        tools=[_INTENT_TOOL],
        tool_choice="required",
        max_tokens=512,
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        return json.loads(msg.tool_calls[0].function.arguments)

    return {"intent_type": "general"}


# ── Permission info builder ───────────────────────────────────────────────────

def _build_permission_info(user: AuthUser, projects: list[dict], action: str | None) -> dict:
    """Return a structured permissions breakdown for the current user."""
    project_names = [p["name"] for p in projects]

    add_detail = (
        "As an admin, you can create alerts in any project in the system."
        if user.is_admin else
        (f"You can create alerts in your assigned project(s): {', '.join(project_names)}."
         if project_names else
         "You have no projects assigned, so you cannot create alerts right now.")
    )
    delete_detail = (
        "As an admin, you can delete any alert system-wide."
        if user.is_admin else
        (f"You can delete alerts within your assigned project(s): {', '.join(project_names)}."
         if project_names else
         "You have no projects assigned, so you cannot delete any alerts.")
    )
    modify_detail = (
        "As an admin, you can modify all aspects of any alert — including severity, assignment, status, and comments."
        if user.is_admin else
        (f"You can assign alerts and add comments within your project(s): {', '.join(project_names)}. "
         "Note: changing alert severity is restricted to admins."
         if project_names else
         "You have no projects assigned, so you cannot modify any alerts.")
    )

    all_perms = {
        "add_alert": {
            "allowed": bool(project_names) or user.is_admin,
            "scope": "any project" if user.is_admin else "assigned projects only",
            "accessible_projects": project_names,
            "detail": add_detail,
        },
        "delete_alert": {
            "allowed": bool(project_names) or user.is_admin,
            "scope": "any alert system-wide" if user.is_admin else "alerts in your assigned projects only",
            "accessible_projects": project_names,
            "detail": delete_detail,
        },
        "modify_alert": {
            "allowed": bool(project_names) or user.is_admin,
            "scope": "any alert system-wide" if user.is_admin else "alerts in your assigned projects only",
            "accessible_projects": project_names,
            "can_change_severity": user.is_admin,
            "can_assign_alert": True,
            "can_add_comment": True,
            "detail": modify_detail,
        },
    }

    action_map = {"add": ["add_alert"], "delete": ["delete_alert"], "modify": ["modify_alert"]}
    keys = action_map.get(action or "all", list(all_perms.keys()))  # type: ignore[arg-type]
    permissions = {k: all_perms[k] for k in keys if k in all_perms}

    return {
        "user_role": user.role,
        "user_name": user.full_name,
        "permissions": permissions,
    }


# ── Data fetcher ──────────────────────────────────────────────────────────────

def _fetch_data(user: AuthUser, intent: dict, projects: list[dict]) -> dict:
    """Fetch the appropriate data based on extracted intent."""
    intent_type = intent.get("intent_type", "general")

    if intent_type == "check_permission":
        return {
            "type": "permission_info",
            "data": _build_permission_info(user, projects, intent.get("permission_action")),
        }

    if intent_type == "summary":
        return {
            "type": "summary",
            "data": get_alert_summary(user),
            "projects": get_projects_for_user(user),
        }

    if intent_type == "project_info":
        return {
            "type": "project_info",
            "data": get_projects_for_user(user),
        }

    if intent_type == "project_assignments":
        return {
            "type": "project_assignments",
            "data": get_project_assignments(user),
        }

    if intent_type == "manager_alert_stats":
        return {
            "type": "manager_alert_stats",
            "data": get_alerts_by_manager(user),
        }

    if intent_type == "create_alert":
        result = create_alert(
            user=user,
            project_name=intent.get("project_name") or "",
            title=intent.get("new_alert_title") or "Untitled Alert",
            description=intent.get("new_alert_description") or "",
            severity=intent.get("severity") or "medium",
            category=intent.get("category") or "general",
            assigned_to=intent.get("assigned_to"),
        )
        return {"type": "create_alert", "data": result}

    if intent_type == "assign_alert":
        result = assign_alert(
            user=user,
            alert_id=intent.get("alert_id") or 0,
            assigned_to=intent.get("assigned_to") or "",
        )
        return {"type": "assign_alert", "data": result}

    if intent_type == "add_comment":
        result = add_alert_comment(
            user=user,
            alert_id=intent.get("alert_id") or 0,
            comment_text=intent.get("comment_text") or "",
        )
        return {"type": "add_comment", "data": result}

    if intent_type == "get_comments":
        result = get_alert_comments(
            user=user,
            alert_id=intent.get("alert_id") or 0,
        )
        return {"type": "get_comments", "data": result}

    if intent_type == "update_severity":
        result = update_alert_severity(
            user=user,
            alert_id=intent.get("alert_id") or 0,
            new_severity=intent.get("severity") or "",
        )
        return {"type": "update_severity", "data": result}

    if intent_type == "delete_alert":
        result = delete_alert(
            user=user,
            alert_id=intent.get("alert_id") or 0,
        )
        return {"type": "delete_alert", "data": result}

    if intent_type == "specific_alert" and intent.get("alert_id"):
        alert = get_alert_by_id(user, intent["alert_id"])
        return {
            "type": "specific_alert",
            "data": alert,
        }

    alerts = get_alerts(
        user=user,
        project_name=intent.get("project_name"),
        severity=intent.get("severity"),
        status=intent.get("status"),
        category=intent.get("category"),
        date_from=intent.get("date_from"),
        date_to=intent.get("date_to"),
        limit=min(int(intent.get("limit") or 20), 50),
    )
    return {
        "type": "alert_list",
        "data": alerts,
        "filters_applied": {k: v for k, v in intent.items() if v and k != "intent_type"},
    }


# ── Response generator ────────────────────────────────────────────────────────

def _format_data_for_prompt(fetched: dict) -> str:
    return f"```json\n{json.dumps(fetched, indent=2, default=str)}\n```"


def chat(
    user: AuthUser,
    user_message: str,
    conversation_history: list[dict],
) -> tuple[str, list[dict]]:
    """
    Main chat function.

    Args:
        user: Authenticated user (carries RBAC context).
        user_message: The user's latest message.
        conversation_history: List of {"role": ..., "content": ...} dicts.

    Returns:
        (assistant_reply, updated_conversation_history)
    """
    client = _get_client()
    projects = get_projects_for_user(user)
    system_prompt = _build_system_prompt(user, projects)

    # 1. Extract intent
    intent = _extract_intent(user_message, conversation_history)

    # 2. Fetch relevant data
    fetched = _fetch_data(user, intent, projects)

    # 3. Build augmented user message with data context
    data_context = _format_data_for_prompt(fetched)
    augmented_message = (
        f"{user_message}\n\n"
        f"<retrieved_data>\n{data_context}\n</retrieved_data>\n\n"
        f"Use the retrieved data above to answer the user's question accurately. "
        f"Do not expose raw JSON — present it in a clear, human-readable format."
    )

    # 4. Call Groq for the final response
    messages = [{"role": "system", "content": system_prompt}] + conversation_history + [
        {"role": "user", "content": augmented_message}
    ]

    response = client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        max_tokens=2048,
    )

    assistant_reply = response.choices[0].message.content

    # 5. Update history (store original user message, not augmented)
    updated_history = conversation_history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_reply},
    ]

    return assistant_reply, updated_history


def get_greeting(user: AuthUser) -> str:
    """Generate a personalized greeting with a quick status snapshot."""
    summary = get_alert_summary(user)
    projects = get_projects_for_user(user)

    open_criticals = next(
        (s["count"] for s in summary["by_severity"] if s["severity"] == "critical"), 0
    )
    total_open = next(
        (s["count"] for s in summary["by_status"] if s["status"] == "open"), 0
    )

    role_desc = "Admin" if user.is_admin else "Project Manager"
    project_scope = (
        "all projects" if user.is_admin
        else f"{len(projects)} project(s): {', '.join(p['name'] for p in projects)}"
    )

    urgency = ""
    if open_criticals > 0:
        urgency = f"\n\n**Heads up:** There are **{open_criticals} critical** open alert(s) that may need immediate attention."

    return (
        f"Welcome back, **{user.full_name}** ({role_desc})!\n\n"
        f"You have access to **{project_scope}**.\n"
        f"Currently there are **{total_open} open alert(s)** across your projects.{urgency}\n\n"
        f"What would you like to know? You can ask things like:\n"
        f"- *\"Show me all critical alerts\"*\n"
        f"- *\"What are the open security issues?\"*\n"
        f"- *\"Give me a summary of alerts by project\"*\n"
        f"- *\"List alerts for Alpha Portal this week\"*"
    )
