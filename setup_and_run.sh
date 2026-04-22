#!/bin/bash
# AlertBot — One-step setup & launch script
set -e

echo "🚨 AlertBot Setup"
echo "=================="

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is required. Please install it first."
    exit 1
fi

# Create .env if not present
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  Created .env from .env.example"
    echo "   Please open .env and set your ANTHROPIC_API_KEY, then re-run this script."
    echo ""
    exit 1
fi

# Check API key is set
if grep -q "your_anthropic_api_key_here" .env; then
    echo "⚠️  Please set your ANTHROPIC_API_KEY in the .env file before running."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt --quiet

# Seed DB (if needed)
echo "🗄️  Initializing database..."
python3 -c "
import sys; sys.path.insert(0, '.')
from database.seed import init_db, seed_db, get_connection, DB_PATH
init_db()
conn = get_connection()
count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
conn.close()
if count == 0:
    seed_db()
    print('✅ Database seeded with sample data.')
else:
    print(f'✅ Database already has {count} users — skipping seed.')
"

echo ""
echo "✅ Setup complete! Launching AlertBot..."
echo "   Open http://localhost:8501 in your browser."
echo ""
echo "   Demo logins:"
echo "     alice_admin / admin123  (Admin — all projects)"
echo "     carol_pm   / carol123   (PM — Alpha Portal, Beta Analytics)"
echo "     david_pm   / david123   (PM — Gamma Migration, Delta Security)"
echo ""

streamlit run app.py
