import json
import sys

with open(sys.argv[1], "r") as file:
    lines = [line.rstrip() for line in file]

result = {"used_offsets": [], "used_widths": [], "responses": []}

for line in lines:
    if not line.startswith("time"):
        continue
    time, occ, tail = line.partition(" | ")
    offset, occ, tail = tail.partition(" | ")
    pulse, occ, response = tail.partition(" | ")
    
    # strip key
    result["used_offsets"].append(offset[8:])
    result["used_widths"].append(pulse[7:])
    result["responses"].append(response[11:].strip("'").strip("\\n"))

with open("parsed_logs.txt", "w") as file:
    file.write(json.dumps(result))