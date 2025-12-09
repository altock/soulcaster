#!/usr/bin/env python3
"""Quick test to create a single GitHub issue"""

import requests
import sys

if len(sys.argv) != 3:
    print("Usage: python test_create_one_issue.py <repo_owner/repo_name> <token>")
    sys.exit(1)

repo = sys.argv[1]  # e.g., "naga-k/bad-ux-mart"
token = sys.argv[2]

url = f"https://api.github.com/repos/{repo}/issues"
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

issue = {
    "title": "Test issue from Soulcaster",
    "body": "This is a test issue to verify GitHub API permissions are working correctly.",
    "labels": ["test"]
}

print(f"Creating test issue in {repo}...")
print(f"URL: {url}")

try:
    response = requests.post(url, json=issue, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 201:
        data = response.json()
        print(f"✅ Success! Issue created: {data['html_url']}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 404:
            print("\n💡 Token doesn't have access to this repo or repo doesn't exist")
        elif response.status_code == 401:
            print("\n💡 Token is invalid or expired")
        elif response.status_code == 403:
            print("\n💡 Token doesn't have 'issues' write permission")

except Exception as e:
    print(f"❌ Error: {e}")
