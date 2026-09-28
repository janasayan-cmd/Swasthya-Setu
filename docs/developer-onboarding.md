# HealthSetu — Developer Onboarding Guide

## 1. Welcome to HealthSetu

This guide provides instructions for software engineers joining the HealthSetu backend development team. HealthSetu is a critical healthcare platform; adhering to security rules, coding standards, and clinical safety boundaries is mandatory.

---

## 2. Local Environment Setup

### Prerequisites
- **Python**: Version `3.12` or higher.
- **Git**: Configured with signing keys for commits.
- **Node.js** (Optional): For running the local frontend mock.
- **PostgreSQL / Docker** (Optional): For running a local database instance.

### Step-by-Step Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/kamanasis/HealthSetu.git
   cd HealthSetu
   ```

2. **Create and Activate Virtual Environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -e ".[dev]"
   ```

4. **Configure Local Environment File**:
   Copy the example configuration:
   ```bash
   cp .env.example .env
   ```
   For local development:
   - `APP_ENV=development`
   - `DEBUG=true`
   - `DATABASE_URL` can point to local SQLite/PostgreSQL or test mock.

---

## 3. Running the Application Locally

Start the FastAPI local development server with hot reload:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify service startup:
- **Liveness Probe**: `GET http://127.0.0.1:8000/api/v1/health` $\longrightarrow$ `{"status": "ok", "version": "1.0.0"}`
- **Interactive Swagger UI**: Navigate to `http://127.0.0.1:8000/docs`
- **ReDoc Interactive Docs**: Navigate to `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`

---

## 4. Test Execution & Quality Standards

Always run the full test suite before committing code:
```bash
# Run all tests
pytest -v

# Run targeted test suites
pytest tests/test_auth.py
pytest tests/test_clinical_workflow.py
pytest tests/test_phase20_go_live.py

# Run with test coverage report
pytest --cov=app tests/
```

---

## 5. Coding Conventions & Best Practices

1. **Type Annotations**: All functions, methods, and endpoint signatures must have complete Python type annotations (e.g. `async def get_patient(patient_id: str, db: AsyncSession) -> PatientResponse:`).
2. **Pydantic Validation**: All request payloads and response bodies must use validated Pydantic schemas defined under `app/schemas/`. Do not pass raw dictionaries into service layers.
3. **Structured Logging**: Use `logger = get_logger(__name__)`. Never log raw strings with sensitive data or use standard `print()` statements.
4. **Asynchronous I/O**: All database, storage, and network HTTP operations must be non-blocking (`async` / `await`).
5. **No Competing Database Schemas**: Never create ad-hoc database migrations or alter existing tables without coordinating with the Database Team.

---

## 6. Non-Negotiable Security Rules

- **Zero Secret Commits**: Never commit credentials, passwords, private keys, or API tokens to Git.
- **Fail-Closed Principle**: When a security check fails, deny access immediately.
- **Zero PHI in Logs**: Never log patient names, email addresses, phone numbers, government IDs, or clinical notes in application logs.
- **IDOR Protection**: Always verify that the authenticated actor is authorized to access the specific patient or resource identifier provided in path parameters.

---

## 7. Mandatory Clinical Safety Boundaries

Every engineer working on HealthSetu MUST memorize these clinical boundaries:

1. **Medication Safety Engine Failure $\longrightarrow$ `NOT CLEAR`**: If an interaction check fails, the result is `UNKNOWN` or `ERROR`, NEVER `CLEAR`.
2. **Missing Clinical Data $\longrightarrow$ `NOT NORMAL`**: Missing vitals or clinical context must flag `INSUFFICIENT_INFORMATION`. Never guess or assume normal.
3. **Extracted Data $\longrightarrow$ `NOT Verified`**: Scanned text and OCR extractions always start in unverified states (`is_verified=False`).
4. **AI Output $\longrightarrow$ `NOT Clinical Truth`**: Generative AI provides advisory assistance. It is prohibited from autonomous diagnosis or prescribing.
5. **Triage $\longrightarrow$ `NOT Diagnosis`**: Triage calculates operational urgency (Emergency, Urgent, Routine), never a definitive medical diagnosis.
6. **Transfer $\longrightarrow$ `NOT Automatic`**: Inter-facility transfers require explicit two-sided clinician review and acceptance.
