"""
Minimal vs Detailed Prompt Demo
Generates the same FastAPI microservice twice — once with a minimal prompt,
once with a detailed prompt — and tests both against the same pytest suite.
"""

import os
import re
import json
import time
import subprocess
import tempfile
from openai import OpenAI

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "private/nvidia/nemotron-3-super-120b-a12b"
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

CLIENT = OpenAI(
    base_url=NVIDIA_BASE_URL,
    api_key=NVIDIA_API_KEY,
    default_headers={"NVCF-POLL-SECONDS": "1800"},
)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

MINIMAL_PROMPT = """Create a FastAPI user registration service with three endpoints:
- POST /register (accepts JSON with "name" and "email", returns user with generated "id")
- GET /user/{user_id} (returns user by id, 404 if not found)
- DELETE /user/{user_id} (deletes user by id, 404 if not found)

Use an in-memory dictionary for storage. Return only the Python code, nothing else."""

DETAILED_PROMPT = """Create a FastAPI user registration service. Follow these specifications exactly:

## Architecture
- Single file FastAPI application
- In-memory dictionary storage with string keys
- UUID4 for user ID generation

## Data Models
Use Pydantic BaseModel for request/response schemas:
- UserCreate: name (str, required, min 1 char), email (str, required, must contain @)
- UserResponse: id (str), name (str), email (str)
- ErrorResponse: detail (str)

## API Endpoints

### POST /register
- Request body: UserCreate schema
- Validate that name is not empty and email contains @
- Generate UUID4 string as user ID
- Store in dictionary as {id: {"id": id, "name": name, "email": email}}
- Return UserResponse with status 201
- On validation failure return 422

### GET /user/{user_id}
- Path parameter: user_id (str)
- Look up user in dictionary
- Return UserResponse with status 200
- If not found, raise HTTPException with status 404 and detail "User not found"

### DELETE /user/{user_id}
- Path parameter: user_id (str)
- Remove user from dictionary
- Return {"message": "User deleted"} with status 200
- If not found, raise HTTPException with status 404 and detail "User not found"

## Error Handling Conventions
- Use FastAPI's HTTPException for all error responses
- Always include "detail" key in error responses
- Use appropriate HTTP status codes (201 for creation, 200 for success, 404 for not found, 422 for validation)

## Code Style
- Use type hints on all functions
- Group imports at top: stdlib, then third-party
- Add docstrings to each endpoint function
- Name the FastAPI instance "app"
- Name the storage dictionary "users_db"

## Response Format Examples
POST /register response: {"id": "abc-123", "name": "John", "email": "john@example.com"}
GET /user/{id} response: {"id": "abc-123", "name": "John", "email": "john@example.com"}
DELETE /user/{id} response: {"message": "User deleted"}
GET /user/{id} 404 response: {"detail": "User not found"}

Return only the Python code, nothing else."""

# ---------------------------------------------------------------------------
# Test suite (same for both)
# ---------------------------------------------------------------------------

TEST_CODE = '''"""Test suite for user registration microservice."""
import pytest
from fastapi.testclient import TestClient
from service import app

client = TestClient(app)

# --- Registration Tests ---

def test_register_user():
    """Basic registration returns 201 and user data."""
    response = client.post("/register", json={"name": "Alice", "email": "alice@example.com"})
    assert response.status_code == 201 or response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"

def test_register_returns_unique_ids():
    """Two registrations produce different IDs."""
    r1 = client.post("/register", json={"name": "Bob", "email": "bob@example.com"})
    r2 = client.post("/register", json={"name": "Carol", "email": "carol@example.com"})
    assert r1.json()["id"] != r2.json()["id"]

def test_register_missing_email():
    """Registration without email fails."""
    response = client.post("/register", json={"name": "Dave"})
    assert response.status_code == 422 or response.status_code == 400

def test_register_missing_name():
    """Registration without name fails."""
    response = client.post("/register", json={"email": "eve@example.com"})
    assert response.status_code == 422 or response.status_code == 400

# --- Get User Tests ---

def test_get_user():
    """Registered user can be retrieved."""
    reg = client.post("/register", json={"name": "Frank", "email": "frank@example.com"})
    user_id = reg.json()["id"]
    response = client.get(f"/user/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Frank"
    assert data["email"] == "frank@example.com"

def test_get_user_not_found():
    """Non-existent user returns 404."""
    response = client.get("/user/nonexistent-id-12345")
    assert response.status_code == 404

def test_get_user_has_detail():
    """404 response includes detail message."""
    response = client.get("/user/nonexistent-id-12345")
    assert "detail" in response.json()

# --- Delete User Tests ---

def test_delete_user():
    """Registered user can be deleted."""
    reg = client.post("/register", json={"name": "Grace", "email": "grace@example.com"})
    user_id = reg.json()["id"]
    response = client.delete(f"/user/{user_id}")
    assert response.status_code == 200

def test_delete_user_not_found():
    """Deleting non-existent user returns 404."""
    response = client.delete("/user/nonexistent-id-12345")
    assert response.status_code == 404

def test_delete_then_get():
    """Deleted user cannot be retrieved."""
    reg = client.post("/register", json={"name": "Hank", "email": "hank@example.com"})
    user_id = reg.json()["id"]
    client.delete(f"/user/{user_id}")
    response = client.get(f"/user/{user_id}")
    assert response.status_code == 404
'''

# ---------------------------------------------------------------------------
# Generation and testing
# ---------------------------------------------------------------------------

def extract_code(text: str) -> str:
    """Extract Python code from LLM response."""
    # Try to find code block
    match = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no code block, assume entire response is code
    return text.strip()


def generate_service(prompt: str, label: str) -> tuple[str, float, int]:
    """Generate a microservice from a prompt. Returns (code, time, tokens)."""
    print(f"\n  Generating with {label} prompt...")

    start = time.time()
    response = CLIENT.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a Python developer. Return only valid Python code. No explanations, no markdown formatting unless using a code block."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2048,
    )
    elapsed = time.time() - start

    reply = response.choices[0].message.content
    code = extract_code(reply)
    total_tokens = response.usage.total_tokens if response.usage else 0

    return code, elapsed, total_tokens


def run_tests(service_code: str, test_code: str) -> tuple[int, int, str]:
    """Write service and tests to temp dir, run pytest, return (passed, total, output)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        service_path = os.path.join(tmpdir, "service.py")
        test_path = os.path.join(tmpdir, "test_service.py")

        with open(service_path, "w") as f:
            f.write(service_code)
        with open(test_path, "w") as f:
            f.write(test_code)

        result = subprocess.run(
            ["python3", "-m", "pytest", test_path, "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Count passed/failed
        passed = len(re.findall(r"PASSED", output))
        failed = len(re.findall(r"FAILED", output))
        errors = len(re.findall(r"ERROR", output))
        total = passed + failed + errors

        return passed, total, output


def count_lines(code: str) -> int:
    """Count non-empty, non-comment lines."""
    lines = code.strip().split("\n")
    return sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))


def main():
    if not NVIDIA_API_KEY:
        print("Error: set NVIDIA_API_KEY environment variable")
        return

    print("\n" + "=" * 70)
    print("  MINIMAL vs DETAILED PROMPT EXPERIMENT")
    print("  Model: NVIDIA Nemotron 3 Super (120B/12B active)")
    print("  Task: Generate a FastAPI user registration microservice")
    print("=" * 70)

    # --- Generate with minimal prompt ---
    min_code, min_time, min_tokens = generate_service(MINIMAL_PROMPT, "MINIMAL")
    min_lines = count_lines(min_code)
    print(f"  Generated: {min_lines} lines | {min_tokens} tokens | {min_time:.1f}s")

    # --- Generate with detailed prompt ---
    det_code, det_time, det_tokens = generate_service(DETAILED_PROMPT, "DETAILED")
    det_lines = count_lines(det_code)
    print(f"  Generated: {det_lines} lines | {det_tokens} tokens | {det_time:.1f}s")

    # --- Test both ---
    print("\n" + "-" * 70)
    print("  RUNNING TESTS")
    print("-" * 70)

    print("\n  Testing MINIMAL prompt output...")
    min_passed, min_total, min_output = run_tests(min_code, TEST_CODE)
    print(f"  Result: {min_passed}/{min_total} tests passed")

    print("\n  Testing DETAILED prompt output...")
    det_passed, det_total, det_output = run_tests(det_code, TEST_CODE)
    print(f"  Result: {det_passed}/{det_total} tests passed")

    # --- Comparison ---
    print("\n" + "=" * 70)
    print("  COMPARISON")
    print("=" * 70)
    print(f"  {'Metric':<25} {'Minimal':<20} {'Detailed':<20}")
    print(f"  {'─' * 25} {'─' * 20} {'─' * 20}")
    print(f"  {'Tests passed':<25} {min_passed}/{min_total:<18} {det_passed}/{det_total:<18}")
    print(f"  {'Pass rate':<25} {min_passed/max(min_total,1)*100:.0f}%{'':<17} {det_passed/max(det_total,1)*100:.0f}%")
    print(f"  {'Code lines':<25} {min_lines:<20} {det_lines:<20}")
    print(f"  {'Total tokens':<25} {min_tokens:<20} {det_tokens:<20}")
    print(f"  {'Generation time':<25} {min_time:.1f}s{'':<16} {det_time:.1f}s")

    # --- Verdict ---
    print(f"\n  {'─' * 65}")
    if min_passed >= det_passed:
        if min_passed > det_passed:
            print("  RESULT: Minimal prompt produced MORE correct code")
        else:
            print("  RESULT: Both prompts produced equal correctness")
        if min_lines < det_lines:
            print("  BONUS:  Minimal prompt produced MORE concise code")
    else:
        print("  RESULT: Detailed prompt produced more correct code")

    print()

    # --- Save generated code for inspection ---
    with open("generated_minimal.py", "w") as f:
        f.write(min_code)
    with open("generated_detailed.py", "w") as f:
        f.write(det_code)
    print("  Generated code saved to: generated_minimal.py, generated_detailed.py")

    # --- Save full test output ---
    with open("test_output.txt", "w") as f:
        f.write("=== MINIMAL PROMPT TEST OUTPUT ===\n")
        f.write(min_output)
        f.write("\n\n=== DETAILED PROMPT TEST OUTPUT ===\n")
        f.write(det_output)
    print("  Full test output saved to: test_output.txt")
    print()


if __name__ == "__main__":
    main()
