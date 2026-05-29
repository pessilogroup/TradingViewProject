import os
import sqlite3
import uuid
import datetime
import json

db_path = r"C:\Users\pesil\EAIS\memory\V3_brain.db"
graph_path = r"C:\Users\pesil\EAIS\.agents\cortex\config\mcp_memory_graph.json"

ki_dir = r"c:\Users\pesil\working\mj_trading\TradingViewProject\lobes\knowledge\weex"

print("--- Starting Hybrid and Graph Ingestion ---")

# 1. Read the 5 Knowledge Items
ki_files = [
    ("weex_spot_api.md", "Weex Spot API reference including base URL, headers, order operations, and request/response examples."),
    ("weex_contract_v2_api.md", "Weex Contract V2 API reference covering base URL, _UMCBL suffix, order operations, positions, and V2 migration changelog."),
    ("weex_websocket.md", "Weex WebSocket API specification outlining public tickers subscriptions, tickers payloads, and login authentication."),
    ("weex_signatures.md", "Weex signature calculation mechanism details and executable Python hmac/hashlib/base64 code example."),
    ("weex_quickstart_sandbox.md", "Weex Sandbox (Demo Mode) reference including sandbox URLs, demo keys rules, and mock assets matrix.")
]

kis_data = []
for file_name, summary in ki_files:
    file_path = os.path.join(ki_dir, file_name)
    if not os.path.exists(file_path):
        # try the other location
        file_path = os.path.join(r"C:\Users\pesil\EAIS\lobes\knowledge\weex", file_name)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            kis_data.append((file_name, summary, content))
    else:
        print(f"Error: KI file {file_name} not found!")

# 2. Ingest into L1 Hybrid Memory (V3_brain.db)
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verify table memories structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories';")
        if cursor.fetchone():
            print("Table memories exists in V3_brain.db.")
            
            # Clear previous Weex entries if any
            cursor.execute("DELETE FROM memories WHERE content LIKE '%Weex%' OR summary LIKE '%Weex%'")
            print(f"Removed old Weex memories. Rows affected: {cursor.rowcount}")
            
            for file_name, summary, content in kis_data:
                mem_id = str(uuid.uuid4())
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                metadata_str = json.dumps({"category": "knowledge", "file_name": file_name})
                
                # Check if we should generate a vector_blob. In sqlite-vec, vector_blob is typically a blob of floats
                # We can store a mock vector blob of 1536 floats (or whatever size it expects, or empty)
                # Since we don't have the embedding model online, we'll store a zero vector blob if required, or NULL
                # Let's write the query
                cursor.execute(
                    "INSERT INTO memories (id, summary, content, vector_blob, metadata, ts, integrity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (mem_id, summary, content, None, metadata_str, ts, None)
                )
                print(f"Inserted L1 Memory for {file_name} (ID: {mem_id})")
                
            conn.commit()
            print("L1 Ingestion committed successfully.")
            
            # Verify retrieval
            cursor.execute("SELECT id, summary, ts FROM memories WHERE content LIKE '%Weex%'")
            rows = cursor.fetchall()
            print(f"Verified L1 Memories: retrieved {len(rows)} entries:")
            for r in rows:
                print(f"  ID: {r[0]} | Summary: {r[1]} | TS: {r[2]}")
        else:
            print("Error: memories table not found in V3_brain.db!")
        conn.close()
    except Exception as e:
        print(f"L1 Ingestion failed: {e}")
else:
    print(f"V3_brain.db not found at {db_path}")

# 3. Ingest into Graph Memory (mcp_memory_graph.json)
if os.path.exists(graph_path):
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
            
        print("Loaded graph memory JSON file.")
        
        # Parse entities and relations
        entities = graph_data.get("entities", [])
        relations = graph_data.get("relations", [])
        
        # Prepare target entities
        target_entities = [
            {
                "name": "Weex Exchange",
                "entityType": "exchange",
                "observations": [
                    "Weex is a cryptocurrency trading exchange supporting Spot and Contract Margin trading.",
                    "The Weex API provides REST endpoints and WebSocket streams for public market data and private account management."
                ]
            },
            {
                "name": "Weex Spot API",
                "entityType": "api_module",
                "observations": [
                    "Handles Spot order placement, cancellations, and order detail retrieval.",
                    "The production Spot base URL is https://api.weex.com.",
                    "Requests to the Spot API are structured under /api/v1/spot/*."
                ]
            },
            {
                "name": "Weex Contract V2 API",
                "entityType": "api_module",
                "observations": [
                    "Handles Contract V2 order placement, cancels, positions, and order details.",
                    "USDT-M margin contract symbols are suffixed with _UMCBL.",
                    "Endpoints are structured under /api/v2/contract/*."
                ]
            },
            {
                "name": "Weex WebSocket API",
                "entityType": "api_module",
                "observations": [
                    "Provides real-time public market tickers and private channel order/balance events.",
                    "Spot WebSocket host is wss://ws.weex.com/spot/v1/websocket.",
                    "Contract WebSocket host is wss://ws.weex.com/mix/v1/websocket.",
                    "Private streams require signature-based login authentication."
                ]
            },
            {
                "name": "Weex Signatures",
                "entityType": "auth_mechanism",
                "observations": [
                    "Private REST/WS requests require signature headers: ACCESS-KEY, ACCESS-SIGN, ACCESS-TIMESTAMP, and ACCESS-PASSPHRASE.",
                    "The signature payload format is timestamp + METHOD + requestPath + body.",
                    "Signatures are computed as HMAC-SHA256 of the payload using the API Secret Key, then Base64-encoded."
                ]
            },
            {
                "name": "Weex Sandbox",
                "entityType": "test_environment",
                "observations": [
                    "Provides a paper trading testbed with mock assets (e.g. SBTC, SUSDT).",
                    "Demo base REST URL is https://api-demo.weex.com.",
                    "Demo WebSocket base URL is wss://ws-demo.weex.com/mix/v1/websocket."
                ]
            }
        ]
        
        # Prepare target relations
        target_relations = [
            {"from": "Weex Exchange", "to": "Weex Spot API", "relationType": "exposes"},
            {"from": "Weex Exchange", "to": "Weex Contract V2 API", "relationType": "exposes"},
            {"from": "Weex Exchange", "to": "Weex WebSocket API", "relationType": "exposes"},
            {"from": "Weex Spot API", "to": "Weex Signatures", "relationType": "requires"},
            {"from": "Weex Contract V2 API", "to": "Weex Signatures", "relationType": "requires"},
            {"from": "Weex WebSocket API", "to": "Weex Signatures", "relationType": "requires"},
            {"from": "Weex Exchange", "to": "Weex Sandbox", "relationType": "provides"}
        ]
        
        # Upsert entities
        existing_entities = {e["name"]: e for e in entities}
        for te in target_entities:
            name = te["name"]
            if name in existing_entities:
                # Merge observations
                obs_set = set(existing_entities[name].get("observations", []))
                for o in te["observations"]:
                    obs_set.add(o)
                existing_entities[name]["observations"] = list(obs_set)
                existing_entities[name]["entityType"] = te["entityType"] # ensure correct type
                print(f"Updated existing entity: {name}")
            else:
                entities.append(te)
                print(f"Added new entity: {name}")
                
        # Upsert relations
        existing_relations = set((r["from"], r["to"], r["relationType"]) for r in relations)
        for tr in target_relations:
            rel_tuple = (tr["from"], tr["to"], tr["relationType"])
            if rel_tuple not in existing_relations:
                relations.append(tr)
                print(f"Added relation: {tr['from']} -[{tr['relationType']}]-> {tr['to']}")
            else:
                print(f"Relation already exists: {tr['from']} -[{tr['relationType']}]-> {tr['to']}")
                
        graph_data["entities"] = entities
        graph_data["relations"] = relations
        
        # Write back to file
        with open(graph_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
            
        print("Graph memory ingestion saved successfully.")
        
        # Verify graph memory entities/relations retrieval
        print("\n--- Verifying Graph Ingestion ---")
        verif_names = [te["name"] for te in target_entities]
        found_entities = [e for e in entities if e["name"] in verif_names]
        print(f"Retrieved {len(found_entities)} Weex entities from graph file:")
        for fe in found_entities:
            print(f"  Entity: {fe['name']} (Type: {fe['entityType']})")
            for obs in fe.get("observations", []):
                print(f"    Observation: {obs}")
                
        found_rels = [r for r in relations if r["from"] in verif_names or r["to"] in verif_names]
        print(f"Retrieved {len(found_rels)} Weex relations from graph file:")
        for fr in found_rels:
            print(f"  Relation: {fr['from']} -[{fr['relationType']}]-> {fr['to']}")
            
    except Exception as e:
        print(f"Graph Ingestion failed: {e}")
else:
    print(f"mcp_memory_graph.json not found at {graph_path}")
