import datetime
import pandas as pd
from pymongo import MongoClient

from api_ingestion import MONGO_URI

# =========================================================
# CONFIGURATION
# =========================================================
# 1. MongoDB Atlas Connection URI
connectionstring= "mongodb+srv://{0}:{1}@cluster0.8cxewhg.mongodb.net/?appName=Cluster0"
DB_NAME = "climate_hydrology_db"
COLLECTION_NAME = "raw_telangana_reservoirs"

# 2. Update this to match your exact downloaded CSV file name
CSV_FILE_NAME = "rwl_tele_hr_telangana-sw_006_1991_2020.csv" 

# =========================================================
# CSV TO MONGODB INGESTION PROCESS
# =========================================================
def ingest_csv_to_mongodb():
    print(f"🔌 Connecting to MongoDB Atlas ({DB_NAME})...")
    client = MongoClient(connectionstring.format("nag96of_db_user", "mexQM5b6DCRMLYXg"))
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    print(f"📄 Reading local CSV file: '{CSV_FILE_NAME}'...")
    
    try:
        # Load CSV into Pandas
        df = pd.read_csv(CSV_FILE_NAME)

        # Standardize column headers for NoSQL (lowercase, trim spaces, replace special chars with underscores)
        df.columns = (
            df.columns.str.strip()
            .str.lower()
            .str.replace(" ", "_")
            .str.replace("(", "")
            .str.replace(")", "")
            .str.replace("-", "_")
            .str.replace("/", "_")
        )

        # Add ingestion metadata tags to every document
        df["ingested_at"] = datetime.datetime.utcnow().isoformat()
        df["data_source"] = "Official_Government_CSV"

        # Convert DataFrame rows into NoSQL JSON/dictionary documents
        documents = df.to_dict(orient="records")

        # Clear existing old records and insert fresh records
        print("🧹 Clearing previous records in collection...")
        collection.delete_many({})

        if documents:
            print(f"🚀 Inserting {len(documents)} raw records into MongoDB...")
            collection.insert_many(documents)
            print(f"✅ Success! Loaded {len(documents)} reservoir records into '{COLLECTION_NAME}'.")
        else:
            print("⚠️ Warning: The CSV file was empty. No records inserted.")

    except FileNotFoundError:
        print(f"❌ Error: File '{CSV_FILE_NAME}' not found. Verify the file path and filename.")
    except Exception as e:
        print(f"❌ Ingestion failed due to error: {e}")

if __name__ == "__main__":
    ingest_csv_to_mongodb()