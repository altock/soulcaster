import os
import requests

# New Credentials provided by user
NEW_URL = "https://busy-barnacle-42832.upstash.io"
NEW_TOKEN = "AadQAAIncDJjOTUwZDIxZjZjOTk0MWMwYjlkMmUwYzM2NDg2NjNmZHAyNDI4MzI"

def test_redis(name, url, token):
    print(f"Testing {name} Redis ({url})...")
    
    # Test Read (GET)
    read_url = f"{url}/get/test_key"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(read_url, headers=headers)
        print(f"  Read check: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"  Read check failed: {e}")

    # Test Write (SET)
    write_url = f"{url}/set/test_key/test_value"
    try:
        resp = requests.get(write_url, headers=headers)
        print(f"  Write check: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"  Write check failed: {e}")

if __name__ == "__main__":
    test_redis("New Credentials", NEW_URL, NEW_TOKEN)