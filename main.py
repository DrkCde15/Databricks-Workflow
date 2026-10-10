
import os
import requests
from dotenv import load_dotenv

load_dotenv()

host = os.environ["DATABRICKS_HOST"].rstrip("/")
token = os.environ["DATABRICKS_TOKEN"]




response = requests.get(
    f"{host}/api/2.0/clusters/list-node-types",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30
)

print("Status:", response.status_code)
print(response.json())




response.raise_for_status()

data = response.json()

clusters = data.get("clusters", [])

print(f"\nTotal de clusters: {len(clusters)}")

for cluster in clusters:
    print(
        cluster.get("cluster_name"),
        "| Estado:", cluster.get("state"),
        "| ID:", cluster.get("cluster_id")
    )
