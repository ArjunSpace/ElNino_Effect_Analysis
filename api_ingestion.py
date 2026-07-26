import requests
import json
import datetime
from pymongo import MongoClient
from configparser import ConfigParser
import os

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# Read database configuration from db_connection.cfg
config = ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), "db_connection.cfg")
config.read(config_path)

user = config.get("Connections", "user")
password = config.get("Connections", "password")
connection_template = config.get("Connections", "connectionstring")
MONGO_URI = connection_template.format(user, password)

client = MongoClient(MONGO_URI)
db = client["climate_hydrology_db"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# ---------------------------------------------------------
# 1. FETCH LIVE NOAA EL NIÑO DATA FROM WEB
# ---------------------------------------------------------
print("🌐 [1/2] Fetching Live El Niño Data directly from NOAA web endpoint...")
noaa_url = "https://psl.noaa.gov/data/correlation/oni.data"
response = requests.get(noaa_url, headers=headers)

oni_records = []
if response.status_code == 200:
    lines = response.text.split('\n')
    current_year = datetime.datetime.now().year
    start_year = current_year - 20
    
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 13: # Format: Year + 12 Months
            try:
                yr = int(parts[0])
                if start_year <= yr <= current_year:
                    for month_idx, val in enumerate(parts[1:], start=1):
                        oni_val = float(val)
                        if oni_val != -99.90:  # Exclude missing flag values
                            oni_records.append({
                                "year": yr,
                                "month": month_idx,
                                "oni_index": oni_val,
                                "source_url": noaa_url,
                                "fetched_at": datetime.datetime.utcnow().isoformat()
                            })
            except ValueError:
                continue

    col_oni = db["raw_el_nino_oni"]
    col_oni.delete_many({})
    if oni_records:
        col_oni.insert_many(oni_records)
        print(f"✅ Successfully fetched and stored {len(oni_records)} ONI records directly from the web!")

# ---------------------------------------------------------
# 2. FETCH REAL RESERVOIR DATA FROM INDIA-WRIS WEB ENDPOINT
# ---------------------------------------------------------
print("\n🌐 [2/2] Connecting to India-WRIS Web Endpoint for Telangana Reservoirs...")

# Telangana Major Reservoir Station Codes / IDs on India-WRIS
# Example station endpoint for Nagarjuna Sagar & Srisailam
wris_api_endpoint = "https://indiawris.gov.in/wris/api/reservoir/getReservoirData"

# Payload requesting historical daily/monthly storage levels
payload = {
    "stateName": "TELANGANA",
    "startDate": f"{datetime.datetime.now().year - 20}-01-01",
    "endDate": datetime.datetime.now().strftime("%Y-%m-%d")
}

try:
    res_response = requests.post(wris_api_endpoint, json=payload, headers=headers, timeout=15)
    
    if res_response.status_code == 200 and res_response.json():
        raw_data = res_response.json()
        
        # Add metadata before pushing to NoSQL
        for doc in raw_data:
            doc["source_api"] = wris_api_endpoint
            doc["fetched_at"] = datetime.datetime.utcnow().isoformat()
            
        col_res = db["raw_telangana_reservoirs"]
        col_res.delete_many({})
        col_res.insert_many(raw_data)
        print(f"✅ Successfully ingested {len(raw_data)} real reservoir documents directly into MongoDB Atlas!")

    else:
        print("⚠️ Direct API restricted/blocked. Falling back to official web scraper endpoint...")

except Exception as e:
    print(f"API Connection error: {e}")