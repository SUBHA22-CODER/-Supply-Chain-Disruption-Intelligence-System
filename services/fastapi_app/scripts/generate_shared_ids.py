import json
import os
import uuid

def main():
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "data"
    )
    os.makedirs(data_dir, exist_ok=True)
    shared_file = os.path.join(data_dir, "shared_ids.json")
    
    if os.path.exists(shared_file):
        print("Shared IDs already exist.")
        return

    # Generate 50 stable supplier IDs and names
    suppliers = []
    for i in range(50):
        suppliers.append({
            "id": str(uuid.uuid4()),
            "name": f"Supplier {i:03d}"
        })
        
    # Generate 100 stable SKU IDs and names
    skus = []
    for i in range(100):
        skus.append({
            "id": str(uuid.uuid4()),
            "name": f"SKU-{1000 + i}"
        })

    shared_data = {
        "suppliers": suppliers,
        "skus": skus
    }
    
    with open(shared_file, "w") as f:
        json.dump(shared_data, f, indent=2)
    print(f"Generated shared IDs in {shared_file}")

if __name__ == "__main__":
    main()
