#!/usr/bin/env bash

echo "=== Updating agent.py with Gemini 3.8 Flash & Rate Limit Handling ==="

# 1. Write the updated agent.py script
cat << 'PYEOF' > agent.py
import os
import time
import subprocess
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
    exit(1)

client = genai.Client(api_key=api_key)

def execute_shell(command: str) -> str:
    """Executes a bash shell command inside the Codespace container and returns output."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout if result.stdout else result.stderr
        return output if output else "Command executed with no output."
    except Exception as e:
        return f"Execution error: {str(e)}"

print("=== GitHub Codespace AI Agent Started ===")
print("Type your message or 'exit' to quit.\n")

chat = client.chats.create(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        system_instruction="You are an autonomous AI coding agent in a GitHub Codespace. Use the execute_shell tool whenever you need to inspect files, write code, run tests, or check project status.",
        tools=[execute_shell]
    )
)

while True:
    try:
        user_input = input("Agent > ")
        if user_input.strip().lower() == "exit":
            break

        success = False
        attempts = 0
        while not success and attempts < 3:
            try:
                response = chat.send_message(user_input)
                print(f"\n[Agent]:\n{response.text}\n")
                success = True
            except Exception as req_err:
                if "429" in str(req_err) or "RESOURCE_EXHAUSTED" in str(req_err):
                    attempts += 1
                    print("\n[Rate limit reached (5 RPM free tier). Waiting 15 seconds before retrying...]\n")
                    time.sleep(15)
                else:
                    raise req_err

    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"\n[Error]: {e}\n")
PYEOF

echo "=== Setting up 'wassay' terminal command shortcut ==="

# 2. Add the alias to ~/.bashrc if not already present
if ! grep -q "alias wassay=" ~/.bashrc; then
    echo "alias wassay='python3 /workspaces/Ai-agent/agent.py'" >> ~/.bashrc
fi

echo "=== Update complete! ==="
