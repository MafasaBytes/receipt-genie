"""
Simple quick test script - tests endpoints one by one.
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"

print("Testing Receipt Scanner Backend\n")

# 1. Health check
print("1. Health Check...")
try:
    r = requests.get("http://localhost:8000/health")
    print(f"   Status: {r.status_code} - {r.json()}")
except Exception as e:
    print(f"   ERROR: {e}")
    exit(1)

# 2. Upload (you'll need to provide a PDF)
print("\n2. Upload PDF...")
print("   To test upload, use:")
print(f"   curl -X POST -F 'file=@your_file.pdf' {BASE_URL}/upload/pdf")
print("   Or use the test_backend.py script")

# 3. Test with a sample file_id (if you have one)
print("\n3. Test endpoints with file_id...")
print("   After uploading, you can test:")
print(f"   - Process: POST {BASE_URL}/process/pdf?file_id=YOUR_FILE_ID")
print(f"   - Status: GET {BASE_URL}/process/status/YOUR_JOB_ID")
print(f"   - Receipts: GET {BASE_URL}/process/receipts/YOUR_FILE_ID")
print(f"   - Export CSV: GET {BASE_URL}/export/csv?file_id=YOUR_FILE_ID")
print(f"   - Export Excel: GET {BASE_URL}/export/excel?file_id=YOUR_FILE_ID")

print("\n✓ Backend is running and ready for testing!")

