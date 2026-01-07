"""
Script to import CSV files into ChromaDB collections.

Creates 2 collections:
1. budget_2025 - from Budget_CarmenCloud_20251103_2.csv
2. glhis_2025 - from GLHIS_CarmenCloud_20251103_2.csv

Both with DeptCode and AccCode as metadata for filtering.
"""

import requests
import os
import time

# API base URL
BASE_URL = "http://localhost:8000"

# CSV file configurations
CSV_FILES = [
    {
        "file_path": "example_csv/Budget_CarmenCloud_20251103_2.csv",
        "collection_name": "budget_2025",
        "domain": "budget",
        "content_columns": "BudgetId,DeptCode,AccCode,AccNameE,AccNameT,Group1,Group2,Group3,Group4,Caption,Year,Revision,Amt1,Amt2,Amt3,Amt4,Amt5,Amt6,Amt7,Amt8,Amt9,Amt10,Amt11,Amt12",
        "metadata_columns": "DeptCode,AccCode,Year",
    },
    {
        "file_path": "example_csv/GLHIS_CarmenCloud_20251103_2.csv",
        "collection_name": "glhis_2025",
        "domain": "budget",
        "content_columns": "GlHisId,DeptCode,AccCode,AccNameE,AccNameT,Group1,Group2,Group3,Group4,Year,AccNature,AccType,BfAmt1,Amt1,BfAmt2,Amt2,BfAmt3,Amt3,BfAmt4,Amt4,BfAmt5,Amt5,BfAmt6,Amt6,BfAmt7,Amt7,BfAmt8,Amt8,BfAmt9,Amt9,BfAmt10,Amt10,BfAmt11,Amt11,BfAmt12,Amt12,BfAmt13,Amt13,Dr1,Cr1,Dr2,Cr2,Dr3,Cr3,Dr4,Cr4,Dr5,Cr5,Dr6,Cr6,Dr7,Cr7,Dr8,Cr8,Dr9,Cr9,Dr10,Cr10,Dr11,Cr11,Dr12,Cr12,Dr13,Cr13",
        "metadata_columns": "DeptCode,AccCode,Year",
    },
]


def import_csv(config: dict) -> dict:
    """Import a CSV file into a collection."""
    file_path = config["file_path"]

    # Check if file exists
    if not os.path.exists(file_path):
        # Try with full path
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)
        if os.path.exists(full_path):
            file_path = full_path
        else:
            return {"error": f"File not found: {file_path}"}

    print(f"\nImporting: {file_path}")
    print(f"  Collection: {config['collection_name']}")
    print(f"  Domain: {config['domain']}")

    # Prepare the multipart form data
    with open(file_path, "rb") as f:
        files = {
            "file": (os.path.basename(file_path), f, "text/csv"),
        }
        data = {
            "collection_name": config["collection_name"],
            "domain": config["domain"],
            "content_columns": config["content_columns"],
            "metadata_columns": config["metadata_columns"],
            "delimiter": ",",
            "is_usali": "false",
        }

        response = requests.post(
            f"{BASE_URL}/api/admin/collections/import/csv",
            files=files,
            data=data,
        )

    if response.status_code == 200:
        result = response.json()
        print(f"  Job started: {result['id']}")
        return result
    else:
        print(f"  Error: {response.status_code} - {response.text}")
        return {"error": response.text}


def wait_for_job(job_id: str, timeout: int = 120) -> dict:
    """Wait for an import job to complete."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(f"{BASE_URL}/api/admin/collections/import-jobs/{job_id}")

        if response.status_code == 200:
            job = response.json()
            status = job["status"]
            progress = job["progress"]

            print(f"  Progress: {progress:.1f}% - Status: {status}")

            if status == "completed":
                print(f"  Completed! {job['processed_items']} items imported.")
                return job
            elif status == "failed":
                print(f"  Failed: {job.get('error_message', 'Unknown error')}")
                return job

        time.sleep(2)

    print("  Timeout waiting for job completion")
    return {"error": "timeout"}


def main():
    print("=" * 60)
    print("CSV Collection Import Script")
    print("=" * 60)

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/api/admin/collections/")
        if response.status_code != 200:
            print(f"Error: Server returned {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to {BASE_URL}")
        print("Make sure the backend server is running: cd backend && python main.py")
        return

    # Import each CSV file
    for config in CSV_FILES:
        result = import_csv(config)

        if "error" not in result and "id" in result:
            # Wait for job to complete
            final_result = wait_for_job(result["id"])

            if final_result.get("status") == "completed":
                print(f"  [OK] Collection '{config['collection_name']}' created successfully!")
            else:
                print(f"  [FAILED] Failed to create collection '{config['collection_name']}'")

    print("\n" + "=" * 60)
    print("Import process completed!")
    print("=" * 60)

    # List collections
    response = requests.get(f"{BASE_URL}/api/admin/collections/")
    if response.status_code == 200:
        collections = response.json()
        print("\nAvailable collections:")
        for col in collections:
            print(f"  - {col['name']}: {col['document_count']} docs ({col['domain']})")


if __name__ == "__main__":
    main()
