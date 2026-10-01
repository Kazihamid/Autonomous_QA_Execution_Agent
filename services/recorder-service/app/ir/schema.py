AUTOMATION_IR_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["irSchemaVersion", "scenario", "configuration", "parameters", "elements", "steps", "metadata"],
    "properties": {
        "irSchemaVersion": {"const": "1.0.0"},
        "scenario": {"type": "object", "required": ["id", "name"]},
        "configuration": {"type": "object"},
        "parameters": {"type": "object"},
        "elements": {"type": "object"},
        "steps": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "action"]}},
        "metadata": {"type": "object"}
    }
}
