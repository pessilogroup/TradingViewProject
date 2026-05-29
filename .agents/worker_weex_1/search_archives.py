import os
import tarfile
import fnmatch

legacy_dir = r"C:\Users\pesil\EAIS\Legacy"
working_dir = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_1"
extract_dir = os.path.join(working_dir, "extracted_legacy")

os.makedirs(extract_dir, exist_ok=True)

print(f"Legacy directory: {legacy_dir}")
if not os.path.exists(legacy_dir):
    print("Legacy directory does not exist.")
else:
    files = os.listdir(legacy_dir)
    print(f"Files in Legacy directory: {files}")

    search_terms = ['weex', 'trade_guard', 'API_INTEGRATION_PLAN', 'docs']

    for filename in files:
        if filename.endswith(".tar.gz") or filename.endswith(".tgz"):
            archive_path = os.path.join(legacy_dir, filename)
            print(f"\nInspecting archive: {archive_path}")
            try:
                with tarfile.open(archive_path, "r:gz") as tar:
                    members = tar.getmembers()
                    print(f"Total members: {len(members)}")
                    
                    matched_members = []
                    for member in members:
                        member_name_lower = member.name.lower()
                        for term in search_terms:
                            if term.lower() in member_name_lower:
                                matched_members.append(member)
                                break
                    
                    print(f"Found {len(matched_members)} matching files in {filename}.")
                    for member in matched_members[:50]: # limit printing
                        print(f" - {member.name} ({member.size} bytes)")
                    
                    # Extract matched members
                    for member in matched_members:
                        # Clean up path to prevent path traversal
                        safe_name = os.path.normpath(member.name).replace("..", "")
                        dest_path = os.path.join(extract_dir, filename + "_extracted", safe_name)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        
                        if member.isfile():
                            # Extract file manually to dynamic paths safely
                            with tar.extractfile(member) as source_file:
                                if source_file:
                                    with open(dest_path, "wb") as target_file:
                                        target_file.write(source_file.read())
                                    print(f"Extracted to: {dest_path}")
            except Exception as e:
                print(f"Error reading {filename}: {e}")
