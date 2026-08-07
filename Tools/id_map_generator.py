import csv
from PIL import Image

csv_file = "states_colors.csv"
png_file = "states_cropped.png"
province_data_header = "province_data.h"
province_map_header = "province_map.h"
province_map_source = "province_map.c"

# ------------------------------------------------------------------
# Scan PNG
# ------------------------------------------------------------------
img = Image.open(png_file).convert('RGB')
width, height = img.size
pixels = img.load()

colors_in_map = set()
for y in range(height):
    for x in range(width):
        colors_in_map.add(pixels[x, y])

print(f"PNG contains {len(colors_in_map)} unique colors.")

# ------------------------------------------------------------------
# Read CSV — pure RGB24 matching, no bit depth reduction anywhere
# ------------------------------------------------------------------
color_to_id = {}
provinces   = []
next_id     = 0
skipped     = 0

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        r     = int(row['R'])
        g     = int(row['G'])
        b     = int(row['B'])
        name  = row['StateName']
        color = (r, g, b)

        if color not in colors_in_map:
            skipped += 1
            continue

        if color not in color_to_id:
            color_to_id[color] = next_id
            provinces.append({
                'id':       next_id,
                'name':     name,
                'color':    color,
                'is_water': 0,
                'pixels':   []
            })
            next_id += 1

print(f"Loaded {len(provinces)} land provinces from CSV (skipped {skipped} not in map).")

# ------------------------------------------------------------------
# Process PNG — any color not in CSV is sea
# ------------------------------------------------------------------
province_map = []

for y in range(height):
    for x in range(width):
        color = pixels[x, y]

        if color not in color_to_id:
            color_to_id[color] = next_id
            provinces.append({
                'id':       next_id,
                'name':     f'Sea_{next_id}',
                'color':    color,
                'is_water': 1,
                'pixels':   []
            })
            next_id += 1

        pid = color_to_id[color]
        province_map.append(pid)
        provinces[pid]['pixels'].append((x, y))

land_count = sum(1 for p in provinces if not p['is_water'])
sea_count  = sum(1 for p in provinces if p['is_water'])
print(f"Total: {len(provinces)} provinces ({land_count} land, {sea_count} sea).")

# ------------------------------------------------------------------
# Compute guaranteed-interior center for each province
# ------------------------------------------------------------------
for p in provinces:
    if not p['pixels']:
        p['center_x'] = 0
        p['center_y'] = 0
        continue

    pixel_set = set(p['pixels'])
    n         = len(p['pixels'])
    cx        = round(sum(px for px, py in p['pixels']) / n)
    cy        = round(sum(py for px, py in p['pixels']) / n)

    if (cx, cy) in pixel_set:
        p['center_x'] = cx
        p['center_y'] = cy
    else:
        best      = None
        best_dist = float('inf')
        for px, py in p['pixels']:
            dist = (px - cx) ** 2 + (py - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best      = (px, py)
        p['center_x'], p['center_y'] = best

# ------------------------------------------------------------------
# Generate province_data.h
# ------------------------------------------------------------------
with open(province_data_header, 'w', encoding='utf-8') as f:
    f.write('#ifndef PROVINCE_DATA_H\n')
    f.write('#define PROVINCE_DATA_H\n\n')
    f.write(f'#define PROVINCE_COUNT {len(provinces)}\n\n')
    f.write('typedef struct {\n')
    f.write('    const char*    name;\n')
    f.write('    unsigned int   color;\n')   # full RGB24, no loss
    f.write('    unsigned char  owner;\n')
    f.write('    unsigned char  is_water;\n')
    f.write('    unsigned short center_x;\n')
    f.write('    unsigned short center_y;\n')
    f.write('} Province;\n\n')
    f.write('extern Province provinces[PROVINCE_COUNT];\n\n')
    f.write('#endif\n')

# ------------------------------------------------------------------
# Generate province_data.c — color stored as full RGB24
# ------------------------------------------------------------------
with open('province_data.c', 'w', encoding='utf-8') as f:
    f.write('#include "province_data.h"\n\n')
    f.write('Province provinces[PROVINCE_COUNT] = {\n')

    for i, p in enumerate(provinces):
        r, g, b = p['color']
        rgb24   = (r << 16) | (g << 8) | b
        comma   = ',' if i < len(provinces) - 1 else ''
        f.write(
            f'    {{"{p["name"]}", 0x{rgb24:06X}, 0, {p["is_water"]}, '
            f'{p["center_x"]}, {p["center_y"]}}}{comma}\n'
        )

    f.write('};\n')

# ------------------------------------------------------------------
# Generate province_map.h
# ------------------------------------------------------------------
with open(province_map_header, 'w') as f:
    f.write('#ifndef PROVINCE_MAP_H\n')
    f.write('#define PROVINCE_MAP_H\n\n')
    f.write(f'#define provinceMapLen    {len(province_map) * 2}\n')
    f.write(f'#define provinceMapWidth  {width}\n')
    f.write(f'#define provinceMapHeight {height}\n\n')
    f.write(f'extern const unsigned short provinceMap[{len(province_map)}];\n\n')
    f.write('#endif\n')

# ------------------------------------------------------------------
# Generate province_map.c
# ------------------------------------------------------------------
with open(province_map_source, 'w') as f:
    f.write('#include "province_map.h"\n\n')
    f.write(f'const unsigned short provinceMap[{len(province_map)}] = {{\n')

    for i in range(0, len(province_map), 12):
        line = "    " + ", ".join(f"0x{v:04X}" for v in province_map[i:i + 12])
        if i + 12 < len(province_map):
            line += ","
        f.write(line + "\n")

    f.write('};\n')

print(f"Generated {province_data_header} and province_data.c")
print(f"Generated {province_map_header} and {province_map_source} ({width}x{height} map)")