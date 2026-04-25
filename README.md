# AlertBot 🚨

## AI-Powered Project Alert Chatbot

AlertBot is an intelligent chatbot application that helps teams manage and track project alerts through natural language conversation. Built with **Streamlit**, **Groq LLM (Llama 3.3)**, and **SQLite**, AlertBot provides role-based access control and real-time alert management for project managers and administrators.

---

## Features

✨ **AI-Powered Conversations**
- Natural language interface powered by Groq's Llama 3.3 LLM
- Intelligent query interpretation and context understanding

🔐 **Role-Based Access Control (RBAC)**
- Admin and PM (Project Manager) roles
- Project-level access restrictions
- Secure authentication system

📊 **Alert Management**
- Create, view, and manage project alerts
- Filter alerts by project, severity, and status
- Real-time alert summaries and insights

💬 **Chatbot Capabilities**
- Query alerts in conversational format
- Assign alerts to team members
- Add comments and notes to alerts
- Update alert severity levels
- Get project summaries and statistics

🎨 **User-Friendly Interface**
- Clean, modern chat bubble design
- Responsive layout powered by Streamlit
- Easy-to-use web-based UI

---

## Project Structure

```
AI-AlertBot/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
├── setup_and_run.sh         # One-step setup & launch script
├── .env.example             # Environment variables template
│
├── database/                # Database layer
│   ├── __init__.py
│   ├── schema.py            # SQLite schema definitions
│   └── seed.py              # Sample data initialization
│
├── auth/                    # Authentication module
│   ├── __init__.py
│   └── auth.py              # User authentication & RBAC logic
│
├── chatbot/                 # AI Chat engine
│   ├── __init__.py
│   └── engine.py            # Groq LLM integration & chat logic
│
└── alerts/                  # Alert management layer
    ├── __init__.py
    └── query.py             # RBAC-aware alert queries & operations
```

---

## Installation & Setup

### Prerequisites

- **Python 3.8+**
- **Groq API Key** (free tier available at [groq.com](https://groq.com))

### Quick Start (Automated)

```bash
bash setup_and_run.sh
```

This script will:
1. Check Python installation
2. Create `.env` file from `.env.example`
3. Install dependencies
4. Initialize and seed the database
5. Launch AlertBot

### Manual Setup

1. **Clone or navigate to the project:**
   ```bash
   cd AI-AlertBot
   ```

2. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```

3. **Add your API key to `.env`:**
   ```bash
   # .env
   GROQ_API_KEY=your_groq_api_key_here
   ```

   Get a free API key from [Groq Console](https://console.groq.com)

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Initialize the database:**
   ```bash
   python3 -c "from database.seed import init_db, seed_db; init_db(); seed_db()"
   ```

6. **Run the application:**
   ```bash
   streamlit run app.py
   ```

7. **Open in browser:**
   Navigate to `http://localhost:8501`

---

## Demo Logins

Test the application with these pre-seeded accounts:

| Username      | Password  | Role       | Access                        |
|---------------|-----------|------------|-------------------------------|
| `alice_admin` | `admin123`| Admin      | All projects                  |
| `carol_pm`    | `carol123`| PM         | Alpha Portal, Beta Analytics  |
| `david_pm`    | `david123`| PM         | Gamma Migration, Delta Security |

---

## Usage

### Via the Chat Interface

1. **Login** with your credentials
2. **Start chatting** with AlertBot using natural language:
   - "Show me high severity alerts"
   - "Create a new alert for the Beta Analytics project"
   - "What alerts need review?"
   - "Assign this alert to John"
   - "Update the severity of alert #5 to critical"

3. **View results** in real-time with formatted chat bubbles

### Supported Commands

- **View Alerts**: "Show alerts", "List all alerts", "What alerts exist?"
- **Filter Alerts**: "Show high severity alerts", "Alerts for Project X"
- **Create Alerts**: "Create an alert about...", "New alert for..."
- **Manage Alerts**: "Assign alert", "Update severity", "Add comment"
- **Get Summaries**: "Alert summary", "Project status", "How many open alerts?"

---

## Configuration

### Environment Variables (`.env`)

```bash
# Required: Your Groq API Key
GROQ_API_KEY=your_key_here

# Optional: Database path (defaults to alertbot.db)
# DB_PATH=./alertbot.db

# Optional: Logging level
# LOG_LEVEL=INFO
```

---

## Dependencies

| Package      | Version    | Purpose                          |
|--------------|-----------|----------------------------------|
| streamlit    | >=1.35.0  | Web framework & UI               |
| groq         | >=0.11.0  | LLM API client                   |
| python-dotenv| >=1.0.0   | Environment configuration        |

---

## Architecture

### Authentication Flow
1. User logs in with credentials
2. System validates against SQLite user table
3. AuthUser object stores role (admin/pm) and accessible projects
4. All queries enforce role-based access control

### Query Flow
1. User sends natural language message
2. Groq LLM interprets intent and extracts filters
3. Alert query engine fetches data (with RBAC applied)
4. Response is formatted and displayed in chat

### Database
- **SQLite** for persistent data storage
- **Schema** includes: users, projects, alerts, assignments, comments
- **Seeding** provides sample data for testing

---

## Development

### Project Layout
- **app.py**: Main Streamlit UI entry point
- **auth/**: User authentication and role management
- **chatbot/**: AI engine powered by Groq LLM
- **alerts/**: Query layer with RBAC enforcement
- **database/**: SQLite schema and initialization

### Adding New Features

1. **New Chat Commands**: Update `chatbot/engine.py`
2. **New Database Tables**: Modify `database/schema.py`
3. **New Queries**: Add functions in `alerts/query.py`
4. **UI Changes**: Edit HTML/CSS in `app.py`

---

## Troubleshooting

### "GROQ_API_KEY is not set"
- Ensure `.env` file exists and contains your API key
- Check that `.env` is in the same directory as `app.py`

### Database Connection Error
- Delete `alertbot.db` and re-run setup
- Ensure database directory is writable

### Port Already in Use
- Change Streamlit port: `streamlit run app.py --server.port 8502`

### Authentication Fails
- Verify credentials match the demo logins above
- Check database is initialized: `python3 -c "from database import init_db; init_db()"`

---

## Security Considerations

⚠️ **This is a demo application.** For production use:
- Use proper password hashing (bcrypt, argon2)
- Implement HTTPS/TLS
- Add comprehensive audit logging
- Use a production database (PostgreSQL, MySQL)
- Implement rate limiting and DDoS protection
- Add comprehensive input validation and sanitization
- Store secrets securely (AWS Secrets Manager, HashiCorp Vault)

---

## Performance Notes

- SQLite is suitable for small teams (< 10 concurrent users)
- For larger deployments, migrate to PostgreSQL or MySQL
- LLM response time depends on Groq API latency (~0.5-2 seconds)
- Database queries benefit from indexing on `project_id` and `user_id`

---

## License

This project is provided as-is for educational and demonstration purposes.

---

## Support & Feedback

For issues, questions, or contributions:
1. Check the troubleshooting section above
2. Review the code comments and docstrings
3. Test with demo credentials first
4. Consult the Groq and Streamlit documentation

---

## Future Enhancements

- 📧 Email notifications for alert updates
- 📱 Mobile app support
- 🔔 Web push notifications
- 📈 Advanced analytics and reporting
- 🔗 Slack/Teams integration
- 🌍 Multi-language support
- 🎯 Alert escalation workflows
- ⏰ Scheduled alert checks

---

**Made with ❤️ using Streamlit & Groq**
