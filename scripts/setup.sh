#!/bin/bash
set -e

echo "=== AcmeCorp Target System Setup ==="

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists."
fi

# Activate
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -e .

# Seed database
echo "Seeding database..."
python scripts/seed_database.py

# Seed emails
echo "Seeding emails..."
python scripts/seed_emails.py

# Generate documents (if script exists and documents are missing)
if [ -f "scripts/generate_documents.py" ]; then
    echo "Generating documents..."
    python scripts/generate_documents.py
fi

# Copy .env.example to .env if not present
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
else
    echo ".env already exists."
fi

echo ""
echo "=== Setup complete ==="
echo "Add your ANTHROPIC_API_KEY to .env, then run:"
echo "  python scripts/run_server.py"
