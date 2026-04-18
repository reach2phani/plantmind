import re

incident = "WR-401 welding robot on Line 4 has triggered a weld quality alarm"
equipment_match = re.search(r'\b([A-Z]{1,3}-\d{2,4})\b', incident)
equipment_id = equipment_match.group(1) if equipment_match else None
print("Extracted equipment ID:", equipment_id)