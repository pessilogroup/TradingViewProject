import sqlite3
import os
import json

def test_weex_db_records():
    db_path = r"C:\Users\pesil\EAIS\memory\V3_brain.db"
    assert os.path.exists(db_path), f"Database V3_brain.db does not exist at {db_path}"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories';")
    assert cursor.fetchone() is not None, "memories table does not exist in V3_brain.db"
    
    cursor.execute("SELECT id, summary, content, metadata, integrity FROM memories WHERE content LIKE '%Weex%' OR summary LIKE '%Weex%'")
    rows = cursor.fetchall()
    
    print(f"\nFound {len(rows)} Weex records:")
    for r in rows:
        print(f"  ID: {r[0]} | Summary: {r[1]} | Integrity: {r[4]}")
        
    assert len(rows) >= 5, f"Expected at least 5 Weex records, found {len(rows)}"
    
    # Check that each file is present
    ki_files = [
        "weex_spot_api.md",
        "weex_contract_v2_api.md",
        "weex_websocket.md",
        "weex_signatures.md",
        "weex_quickstart_sandbox.md"
    ]
    
    found_files = []
    for r in rows:
        metadata = json.loads(r[3]) if r[3] else {}
        file_name = metadata.get("file_name")
        if file_name:
            found_files.append(file_name)
            
    for kf in ki_files:
        assert kf in found_files, f"Missing database record for {kf}"
        
    print("Database verification passed successfully!")
    conn.close()

def test_weex_graph_records():
    graph_path = r"C:\Users\pesil\EAIS\.agents\cortex\config\mcp_memory_graph.json"
    assert os.path.exists(graph_path), f"Graph config does not exist at {graph_path}"
    
    with open(graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)
        
    entities = graph_data.get("entities", [])
    relations = graph_data.get("relations", [])
    
    target_entity_names = [
        "Weex Exchange",
        "Weex Spot API",
        "Weex Contract V2 API",
        "Weex WebSocket API",
        "Weex Signatures",
        "Weex Sandbox"
    ]
    
    found_entities = [e["name"] for e in entities if e["name"] in target_entity_names]
    print(f"\nFound {len(found_entities)} Weex entities in graph config:")
    for name in found_entities:
        print(f"  {name}")
        
    assert len(found_entities) == len(target_entity_names), f"Expected {len(target_entity_names)} entities, found {len(found_entities)}"
    
    target_relations = [
        ("Weex Exchange", "Weex Spot API", "exposes"),
        ("Weex Exchange", "Weex Contract V2 API", "exposes"),
        ("Weex Exchange", "Weex WebSocket API", "exposes"),
        ("Weex Spot API", "Weex Signatures", "requires"),
        ("Weex Contract V2 API", "Weex Signatures", "requires"),
        ("Weex WebSocket API", "Weex Signatures", "requires"),
        ("Weex Exchange", "Weex Sandbox", "provides")
    ]
    
    found_relations = []
    for r in relations:
        if (r["from"] in target_entity_names) or (r["to"] in target_entity_names):
            found_relations.append((r["from"], r["to"], r["relationType"]))
            
    print(f"\nFound {len(found_relations)} Weex relations in graph config:")
    for fr in found_relations:
        print(f"  {fr[0]} -[{fr[2]}]-> {fr[1]}")
        
    for tr in target_relations:
        assert tr in found_relations, f"Missing relation: {tr[0]} -[{tr[2]}]-> {tr[1]}"
        
    print("Graph verification passed successfully!")

if __name__ == "__main__":
    try:
        test_weex_db_records()
        test_weex_graph_records()
        print("\nAll verification checks passed.")
    except AssertionError as e:
        print(f"\nVerification Failure: {e}")
        exit(1)
