import os
import sys
import pymongo
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

MONGODB_URL = os.environ.get(
    "MONGODB_URL",
    "mongodb+srv://Huine:Cardly123@cardly.litnfkr.mongodb.net/?appName=Cardly"
)
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "Cardly")

def get_db():
    print(f"Connecting to MongoDB at: {MONGODB_URL.split('@')[-1]}")
    client = pymongo.MongoClient(MONGODB_URL, tlsAllowInvalidCertificates=True)
    return client[MONGODB_DB_NAME]

def do_migrate(db):
    print("\n=== STARTING MIGRATION ===")
    
    # 1. Handling empty legacy 'scans' collection
    collections = db.list_collection_names()
    if "scans" in collections:
        doc_count = db["scans"].count_documents({})
        if doc_count == 0:
            print("Found empty legacy collection 'scans'. Dropping it...")
            db.drop_collection("scans")
            print("Successfully dropped 'scans' collection.")
        else:
            print(f"WARNING: legacy collection 'scans' is NOT empty ({doc_count} documents). Skipping drop.")
    else:
        print("Legacy collection 'scans' does not exist. Skipping.")

    # 2. Renaming owner_id to user_id on digital_cards collection
    if "digital_cards" in collections:
        # Find count of documents to be migrated
        match_count = db["digital_cards"].count_documents({"owner_id": {"$exists": True}})
        print(f"Found {match_count} documents in 'digital_cards' with 'owner_id' field.")
        
        if match_count > 0:
            result = db["digital_cards"].update_many(
                {"owner_id": {"$exists": True}},
                {"$rename": {"owner_id": "user_id"}}
            )
            print(f"Successfully migrated {result.modified_count} documents (renamed 'owner_id' to 'user_id').")
        else:
            print("No documents require 'owner_id' to 'user_id' rename.")
    else:
        print("Error: 'digital_cards' collection not found in database.")

    print("=== MIGRATION COMPLETE ===\n")

def do_rollback(db):
    print("\n=== STARTING ROLLBACK ===")
    
    # 1. Restore legacy 'scans' collection
    collections = db.list_collection_names()
    if "scans" not in collections:
        print("Re-creating empty legacy collection 'scans'...")
        db.create_collection("scans")
        print("Successfully re-created empty 'scans' collection.")
    else:
        print("Legacy collection 'scans' already exists. Skipping.")

    # 2. Rollback user_id to owner_id on digital_cards collection
    if "digital_cards" in collections:
        match_count = db["digital_cards"].count_documents({"user_id": {"$exists": True}})
        print(f"Found {match_count} documents in 'digital_cards' with 'user_id' field.")
        
        if match_count > 0:
            result = db["digital_cards"].update_many(
                {"user_id": {"$exists": True}},
                {"$rename": {"user_id": "owner_id"}}
            )
            print(f"Successfully rolled back {result.modified_count} documents (renamed 'user_id' to 'owner_id').")
        else:
            print("No documents require 'user_id' to 'owner_id' rollback.")
    else:
        print("Error: 'digital_cards' collection not found in database.")

    print("=== ROLLBACK COMPLETE ===\n")

if __name__ == "__main__":
    action = "migrate"
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()

    db = get_db()
    if action == "migrate":
        do_migrate(db)
    elif action == "rollback":
        do_rollback(db)
    else:
        print(f"Invalid action: {action}. Please use 'migrate' or 'rollback'.")
        sys.exit(1)
