#!/bin/bash

echo "=== Starting Agent Dependencies & Skills Installation ==="

# 1. Update package list and install system dependencies
echo "--> Installing system packages..."
sudo apt update && sudo apt install -y git curl python3-pip

# 2. Install Browser-Use and Playwright
echo "--> Installing Browser-Use & Playwright..."
pip install browser-use playwright
python3 -m playwright install --with-deps

# 3. Create Skills Directory
SKILLS_DIR="$HOME/.agent/skills"
mkdir -p "$SKILLS_DIR"

# 4. Install Scientific Agent Skills
echo "--> Installing Scientific Agent Skills..."
git clone https://github.com/k-dense-ai/scientific-agent-skills.git /tmp/scientific-agent-skills
cp -r /tmp/scientific-agent-skills/skills/* "$SKILLS_DIR/" 2>/dev/null || true
rm -rf /tmp/scientific-agent-skills

# 5. Install Anthropic Cybersecurity Skills
echo "--> Installing Cybersecurity Skills..."
git clone https://github.com/mukul975/anthropic-cybersecurity-skills.git /tmp/cybersecurity-skills
cp -r /tmp/cybersecurity-skills/skills/* "$SKILLS_DIR/" 2>/dev/null || true
rm -rf /tmp/cybersecurity-skills

# 6. Install Graph / Agent Memory dependencies
echo "--> Installing Agent Memory dependencies..."
pip install neo4j-agent-memory

# 7. Install Diagram Tools (Mermaid CLI)
echo "--> Installing Diagram Tools (Mermaid CLI)..."
npm install -g @mermaid-js/mermaid-cli || echo "npm not installed, skipping Mermaid CLI"

echo "=== All skills and dependencies successfully installed! ==="
