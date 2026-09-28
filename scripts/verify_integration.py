import asyncio
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.demo_seed import seed_demo_data

async def run_full_integration_test():
    seed_demo_data()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        print("\n================== HEALTHSETU INTEGRATION TEST ==================")
        
        # 1. Health & Readiness checks
        h_res = await client.get("/api/v1/health")
        assert h_res.status_code == 200, f"Health check failed: {h_res.text}"
        print(f"[OK] GET /api/v1/health -> Status: {h_res.status_code}")

        r_res = await client.get("/api/v1/ready")
        assert r_res.status_code == 200, f"Ready check failed: {r_res.text}"
        print(f"[OK] GET /api/v1/ready  -> Status: {r_res.status_code}")

        # 2. Authentication for all 3 demo personas
        auth_patient = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "patient@healthsetu.org", "password": "StrongP@ssw0rd123!"}
        )
        assert auth_patient.status_code == 200, f"Patient login failed: {auth_patient.text}"
        pat_token = auth_patient.json()["data"]["access_token"]
        print("[OK] POST /api/v1/auth/login (patient@healthsetu.org) -> 200 OK")

        auth_doctor = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "doctor@healthsetu.org", "password": "StrongP@ssw0rd123!"}
        )
        assert auth_doctor.status_code == 200, f"Doctor login failed: {auth_doctor.text}"
        doc_token = auth_doctor.json()["data"]["access_token"]
        print("[OK] POST /api/v1/auth/login (doctor@healthsetu.org)  -> 200 OK")

        auth_admin = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "admin@healthsetu.org", "password": "StrongP@ssw0rd123!"}
        )
        assert auth_admin.status_code == 200, f"Admin login failed: {auth_admin.text}"
        print("[OK] POST /api/v1/auth/login (admin@healthsetu.org)   -> 200 OK")

        pat_headers = {"Authorization": f"Bearer {pat_token}"}
        doc_headers = {"Authorization": f"Bearer {doc_token}"}

        # 3. Patient record, medications, allergies
        p_res = await client.get("/api/v1/patients/HS-PAT-8921", headers=pat_headers)
        assert p_res.status_code == 200, f"Patient fetch failed: {p_res.text}"
        p_data = p_res.json()["data"]
        full_name = f"{p_data.get('first_name', '')} {p_data.get('last_name', '')}".strip()
        print(f"[OK] GET /api/v1/patients/HS-PAT-8921 -> Patient: {full_name} (ID: {p_data['id']})")

        meds_res = await client.get("/api/v1/patients/HS-PAT-8921/medications", headers=pat_headers)
        assert meds_res.status_code == 200, f"Medications failed: {meds_res.text}"
        meds = meds_res.json()["data"]["items"]
        med_names = [m.get("drug_name_raw") or m.get("name") or (m.get("normalized_info") or {}).get("canonical_name") for m in meds]
        print(f"[OK] GET /api/v1/patients/HS-PAT-8921/medications -> {len(meds)} active medications: {med_names}")

        allergies_res = await client.get("/api/v1/patients/HS-PAT-8921/allergies", headers=pat_headers)
        assert allergies_res.status_code == 200, f"Allergies failed: {allergies_res.text}"
        allergies = allergies_res.json()["data"]["items"]
        substances = [a.get("substance") or a.get("allergen") for a in allergies]
        print(f"[OK] GET /api/v1/patients/HS-PAT-8921/allergies -> {len(allergies)} verified allergies: {substances}")

        # 4. Consents grant and list
        consents_res = await client.get("/api/v1/consents", headers=pat_headers)
        assert consents_res.status_code == 200, f"Consents fetch failed: {consents_res.text}"
        consents = consents_res.json()["data"]["items"]
        print(f"[OK] GET /api/v1/consents -> {len(consents)} consent artifacts: {[c['id'] for c in consents]}")

        # 5. Doctor Clinical Workspace
        ws_res = await client.get("/api/v1/patients/HS-PAT-8921/clinical-workspace", headers=doc_headers)
        assert ws_res.status_code == 200, f"Clinical workspace failed: {ws_res.text}"
        ws = ws_res.json()["data"]
        pat_info = ws.get("patient", {})
        ws_pat_name = f"{pat_info.get('first_name', '')} {pat_info.get('last_name', '')}".strip() or pat_info.get("name", "Unknown")
        print(f"[OK] GET /clinical-workspace -> Patient: {ws_pat_name}, Vitals: {len(ws.get('vitals', []))}")

        # 6. Prospective Medication Safety Check (e.g. Ibuprofen triggers NSAID hypersensitivity warning)
        safety_payload = {
            "medications": [{"name": "Ibuprofen", "strength": "400mg", "route": "Oral"}],
            "include_current_medications": True
        }
        safety_res = await client.post(
            "/api/v1/patients/HS-PAT-8921/medication-safety/check-medications",
            json=safety_payload,
            headers=doc_headers
        )
        assert safety_res.status_code == 200, f"Safety check failed: {safety_res.text}"
        safety_eval = safety_res.json()["data"]
        alerts = safety_eval.get("alerts", [])
        print(f"[OK] POST /medication-safety/check-medications -> Evaluated successfully. {len(alerts)} alerts generated:")
        for alert in alerts:
            print(f"     * [{alert.get('severity')}] {alert.get('title')}: {alert.get('description', '')[:70]}...")

        # 7. Healthcare Facilities Search & Discovery
        fac_res = await client.get("/api/v1/facilities/search", headers=doc_headers)
        assert fac_res.status_code == 200, f"Facility search failed: {fac_res.text}"
        facs = fac_res.json()["data"]["items"]
        fac_names = [f["name"] for f in facs]
        print(f"[OK] GET /api/v1/facilities/search -> {len(facs)} facilities: {fac_names}")

        disc_res = await client.get("/api/v1/facilities/discover", headers=pat_headers)
        assert disc_res.status_code == 200, f"Facility discover failed: {disc_res.text}"
        disc_items = disc_res.json()["data"]["items"]
        print(f"[OK] GET /api/v1/facilities/discover -> {len(disc_items)} facilities discovered")

        print("================== ALL INTEGRATION CHECKS PASSED ==================\n")

if __name__ == "__main__":
    asyncio.run(run_full_integration_test())
