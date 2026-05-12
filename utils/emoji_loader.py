import os
import json

def scan_emojis(base_path="emojis"):
    groups = {}
    if not os.path.exists(base_path):
        return groups

    for folder in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder)
        if os.path.isdir(folder_path):
            group_emojis = []
            for file in os.listdir(folder_path):
                if file.endswith(".json"):
                    try:
                        with open(os.path.join(folder_path, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                group_emojis.extend(data)
                    except Exception as e:
                        print(f"Error reading {file}: {e}")

            if group_emojis:
                groups[folder] = {
                    "preview": group_emojis[0].get("text", "✨"),
                    "emojis": group_emojis
                }
    return groups
