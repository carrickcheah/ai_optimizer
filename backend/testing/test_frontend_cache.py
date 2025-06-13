#!/usr/bin/env python3
"""
Test to verify if frontend cache is the issue by making direct API calls.
"""

import requests
import json
from datetime import datetime

def test_api_directly():
    """Test API directly to bypass frontend cache."""
    print("🔍 TESTING API DIRECTLY (BYPASS FRONTEND CACHE)")
    print("=" * 60)
    
    # Test the API endpoint directly
    api_url = "http://localhost:8000"
    
    try:
        # Test 1: Check if server is running
        response = requests.get(f"{api_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Server error: {response.status_code}")
            return
            
        print()
        
        # Test 2: Try scheduling endpoint
        print("Testing scheduling endpoint...")
        
        # Check available endpoints
        docs_response = requests.get(f"{api_url}/docs", timeout=5)
        if docs_response.status_code == 200:
            print("✅ Docs endpoint accessible")
        
        # Try production jobs endpoint
        prod_response = requests.get(f"{api_url}/api/production-jobs", timeout=5)
        if prod_response.status_code == 200:
            print("✅ Production jobs endpoint working")
            jobs = prod_response.json()
            print(f"Found {len(jobs)} jobs")
            
            if jobs:
                # Show first job details
                first_job = jobs[0]
                print(f"First job: {first_job.get('job_id', 'Unknown')}")
                
        else:
            print(f"❌ Production jobs endpoint error: {prod_response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server")
        print("Make sure the server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    print("CACHE DEBUGGING STEPS:")
    print("1. Open browser DevTools (F12)")
    print("2. Go to Network tab")
    print("3. Refresh your frontend page")
    print("4. Check if API calls are being made")
    print("5. Look for 304 responses (cached) vs 200 (fresh)")
    print("6. Try Ctrl+F5 (hard refresh)")
    print("7. Clear browser cache and cookies")

if __name__ == "__main__":
    test_api_directly()