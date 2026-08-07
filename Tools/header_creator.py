from PIL import Image
import csv
import struct

PNG_FILE = "regions.png"
CSV_FILE = "regions.csv"

OUT_BIN = "region_map.bin"
OUT_HEADER = "region_table.h"


# -----------------------------
# Load CSV
# -----------------------------

color_to_id = {}
id_to_name = {}

with open(CSV_FILE, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)

    for row in reader:
        state_id = int(row[0])
        r = int(row[1])
        g = int(row[2])
        b = int(row[3])
        name = row[4]

        color_to_id[(r, g, b)] = state_id
        id_to_name[state_id] = name


print(f"Loaded {len(id_to_name)} regions.")


# -----------------------------
# Load Image
# -----------------------------

img = Image.open(PNG_FILE).convert("RGB")
width, height = img.size

print("Image size:", width, height)

pixels = img.load()


# -----------------------------
# Build binary map
# -----------------------------

region_bytes = bytearray(width * height)

missing_colors = set()

i = 0
for y in range(height):
    for x in range(width):
        color = pixels[x, y]

        if color not in color_to_id:
            missing_colors.add(color)
            region_id = 0  # fallback
        else:
            region_id = color_to_id[color]

        if region_id > 255:
            raise ValueError("Region ID exceeds 255 — use u16 instead!")

        region_bytes[i] = region_id
        i += 1


if missing_colors:
    print("\nWARNING: Colors found in PNG but NOT in CSV:")
    for c in list(missing_colors)[:20]:
        print(c)
    print("...")

# -----------------------------
# Write binary
# -----------------------------

with open(OUT_BIN, "wb") as f:
    f.write(region_bytes)

print("Wrote", OUT_BIN)


# -----------------------------
# Generate C header
# -----------------------------

max_id = max(id_to_name.keys())

with open(OUT_HEADER, "w", encoding="utf-8") as f:
    f.write("#ifndef REGION_TABLE_H\n")
    f.write("#define REGION_TABLE_H\n\n")

    f.write("static const char* REGION_NAMES[] = {\n")

    for i in range(max_id + 1):
        name = id_to_name.get(i, "Unknown")
        f.write(f'    "{name}",\n')

    f.write("};\n\n")
    f.write("#endif\n")

print("Wrote", OUT_HEADER)
