import os
import json
import logging

_emoji_cache = None

def scan_emojis(base_paths=["emojis", "imoji/emojis"]):
    global _emoji_cache
    if _emoji_cache is not None:
        return _emoji_cache

    groups = {}

    for base_path in base_paths:
        if not os.path.exists(base_path):
            continue

        for folder in os.listdir(base_path):
            folder_path = os.path.join(base_path, folder)
            if not os.path.isdir(folder_path):
                continue

            group_emojis = []
            # Sort files to ensure consistent order
            files = sorted(os.listdir(folder_path))

            for file in files:
                if not file.endswith(".json"):
                    continue

                file_path = os.path.join(folder_path, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            group_emojis.extend(data)
                        elif isinstance(data, dict):
                            group_emojis.append(data)
                except Exception as e:
                    logging.error(f"Error reading {file_path}: {e}")

            if group_emojis:
                # If group already exists from another base_path, merge them
                if folder in groups:
                    groups[folder]["emojis"].extend(group_emojis)
                else:
                    groups[folder] = {
                        "preview": group_emojis[0].get("text", "✨"),
                        "emojis": group_emojis
                    }

    _emoji_cache = groups
    return groups

def clear_emoji_cache():
    global _emoji_cache
    _emoji_cache = None
