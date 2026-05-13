import os
import json
import logging
import asyncio
from database.models import AsyncSessionLocal, CustomEmoji
from sqlalchemy import select

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
                        # Extract ONLY what is needed for the WebApp to avoid 20MB+ responses
                        # If it's a list, process each item
                        items = data if isinstance(data, list) else [data]

                        for item in items:
                            eid = item.get("custom_emoji_id") or item.get("id") or item.get("emoji_id")
                            if eid:
                                group_emojis.append({
                                    "custom_emoji_id": str(eid),
                                    "text": item.get("text") or item.get("shortcut") or "✨"
                                })
                            elif "tgs" in item or "layers" in item:
                                # It's a Lottie file (TGS source).
                                # Use filename as fallback ID if no ID found
                                fallback_id = file.replace(".json", "")
                                group_emojis.append({
                                    "custom_emoji_id": fallback_id,
                                    "text": "✨"
                                })
                except Exception as e:
                    logging.error(f"Error reading {file_path}: {e}")

            if group_emojis:
                if folder in groups:
                    groups[folder]["emojis"].extend(group_emojis)
                else:
                    groups[folder] = {
                        "preview": group_emojis[0].get("text", "✨"),
                        "emojis": group_emojis
                    }

    _emoji_cache = groups
    return groups

async def get_all_emojis():
    """Returns filesystem emojis merged with database emojis."""
    fs_groups = scan_emojis()

    # Fetch from database
    db_emojis = []
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(CustomEmoji)
            result = await session.execute(stmt)
            db_emojis = result.scalars().all()
    except Exception as e:
        logging.error(f"Error fetching database emojis: {e}")

    if db_emojis:
        db_list = []
        for e in db_emojis:
            db_list.append({
                "custom_emoji_id": str(e.custom_emoji_id),
                "text": e.shortcut or "✨"
            })

        if "المستوردة 📥" in fs_groups:
            fs_groups["المستوردة 📥"]["emojis"].extend(db_list)
        else:
            fs_groups["المستوردة 📥"] = {
                "preview": "📥",
                "emojis": db_list
            }

    return fs_groups

def clear_emoji_cache():
    global _emoji_cache
    _emoji_cache = None
