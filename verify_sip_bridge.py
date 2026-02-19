import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000"
API_KEY = "your_api_key_here"  # Need to replace with a real one during testing

async def test_exotel_trunk_creation():
    url = f"{BASE_URL}/sip/create-outbound-trunk"
    headers = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
    payload = {
        "trunk_name": "Test Exotel",
        "trunk_type": "exotel",
        "trunk_config": {
            "exotel_number": "08044319240"
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        print(f"Exotel Trunk Creation: {response.status_code}")
        print(response.json())
        return response.json().get("data", {}).get("trunk_id")

async def test_twilio_trunk_creation():
    url = f"{BASE_URL}/sip/create-outbound-trunk"
    headers = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
    payload = {
        "trunk_name": "Test Twilio",
        "trunk_type": "twilio",
        "trunk_config": {
            "address": "pstn.twilio.com",
            "numbers": ["+1234567890"],
            "username": "user",
            "password": "pass"
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        print(f"Twilio Trunk Creation: {response.status_code}")
        print(response.json())
        return response.json().get("data", {}).get("trunk_id")

async def main():
    # Example usage:
    # id = await test_exotel_trunk_creation()
    # print(f"Created Exotel Trunk ID: {id}")
    pass

if __name__ == "__main__":
    # asyncio.run(main())
    print("Verification script ready. Use after starting the API server.")
