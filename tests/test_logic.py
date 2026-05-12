import unittest
import json
from aiogram.types import MessageEntity

def parse_entities(entities_json):
    entities = []
    if entities_json:
        entities_data = json.loads(entities_json)
        for ent in entities_data:
            entities.append(MessageEntity(
                type=ent['type'],
                offset=ent['offset'],
                length=ent['length'],
                custom_emoji_id=ent.get('custom_emoji_id')
            ))
    return entities

class TestEntityParsing(unittest.TestCase):
    def test_parse_custom_emoji(self):
        json_data = json.dumps([
            {
                "type": "custom_emoji",
                "offset": 6,
                "length": 2,
                "custom_emoji_id": "5368324170671202286"
            }
        ])
        entities = parse_entities(json_data)
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].type, "custom_emoji")
        self.assertEqual(entities[0].offset, 6)
        self.assertEqual(entities[0].custom_emoji_id, "5368324170671202286")

if __name__ == "__main__":
    unittest.main()
