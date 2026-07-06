import os
import json
import logging
import asyncio
from database.models import AsyncSessionLocal, CustomEmoji
from sqlalchemy import select

_emoji_cache = None
_mapping_cache = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_mapping():
    global _mapping_cache
    if _mapping_cache is not None:
        return _mapping_cache

    mapping_path = os.path.join(PROJECT_ROOT, "utils", "emoji_mapping.json")
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r") as f:
                _mapping_cache = json.load(f)
                return _mapping_cache
        except Exception as e:
            logging.error(f"Error loading emoji mapping: {e}")
    return {}

def scan_emojis(base_paths=["emojis", "imoji/emojis"]):
    global _emoji_cache
    if _emoji_cache is not None:
        return _emoji_cache

    groups = {}
    mapping = load_mapping()

    # Convert relative base_paths to absolute paths
    abs_base_paths = [os.path.join(PROJECT_ROOT, bp) if not os.path.isabs(bp) else bp for bp in base_paths]

    for base_path in abs_base_paths:
        if not os.path.exists(base_path):
            continue

        for folder in os.listdir(base_path):
            folder_path = os.path.join(base_path, folder)
            if not os.path.isdir(folder_path):
                continue

            group_emojis = []
            # Sort files numerically to ensure consistent order
            try:
                files = sorted(os.listdir(folder_path), key=lambda x: int(os.path.splitext(x)[0]) if x.endswith(".json") and os.path.splitext(x)[0].isdigit() else x)
            except:
                files = sorted(os.listdir(folder_path))

            for file in files:
                if not file.endswith(".json"):
                    continue

                file_id = os.path.splitext(file)[0]
                file_path = os.path.join(folder_path, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Extract ONLY what is needed for the WebApp to avoid 20MB+ responses
                        is_lottie = "tgs" in data or "layers" in data

                        if is_lottie:
                            # Use mapping if available for this group and file
                            mapped_data = mapping.get(folder, {}).get(file_id)
                            if isinstance(mapped_data, dict):
                                real_id = mapped_data.get("id", file_id)
                                emoji_char = mapped_data.get("emoji", "🦆")
                            else:
                                real_id = mapped_data if mapped_data else file_id
                                emoji_char = "🦆"

                            group_emojis.append({
                                "custom_emoji_id": real_id,
                                "file_id": file_id, # Keep original filename for raw data fetch
                                "text": emoji_char,
                                "is_lottie": True,
                                "unique_id": f"duck_{file_id}"
                            })
                        else:
                            # Standard JSON with emoji list or single emoji metadata
                            items = data if isinstance(data, list) else [data]
                            for item in items:
                                eid = item.get("custom_emoji_id") or item.get("id") or item.get("emoji_id") or file_id
                                group_emojis.append({
                                    "custom_emoji_id": str(eid),
                                    "text": item.get("text") or item.get("shortcut") or "✨",
                                    "unique_id": f"emoji_{eid}"
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
                "text": e.shortcut or "✨",
                "unique_id": f"db_{e.custom_emoji_id}"
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
