from PIL import Image
import csv

# Input files
states_bmp = "states_cropped.png"  # or .bmp
states_colors_csv = "states_colors.csv"
output_file = "states_visualization.png"

# Colors
LAND_COLOR = (80, 180, 80)  # Muted green
SEA_COLOR = (100, 150, 220)  # Light blue
BORDER_COLOR = (40, 40, 40)  # Dark gray

print("Step 1: Loading state color mapping...")
color_to_state = {}  # RGB -> (state_id, is_water)

with open(states_colors_csv, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        r = int(row['R'])
        g = int(row['G'])
        b = int(row['B'])
        state_id = int(row['StateID'])

        # Check if StateName contains "Sea_" to determine water
        state_name = row['StateName']
        is_water = 1 if state_name.startswith('Sea_') else 0

        color_to_state[(r, g, b)] = (state_id, is_water)

print(f"  Loaded {len(color_to_state)} state colors")

print("\nStep 2: Loading states bitmap...")
img = Image.open(states_bmp).convert('RGB')
width, height = img.size
pixels = img.load()
print(f"  Image size: {width}x{height}")

print("\nStep 3: Creating visualization...")
new_img = Image.new('RGB', (width, height), (0, 0, 0))
new_pixels = new_img.load()

# First pass: color states
for y in range(height):
    if y % 100 == 0:
        print(f"  Coloring row {y}/{height}...")

    for x in range(width):
        color = pixels[x, y]
        state_info = color_to_state.get(color)

        if state_info:
            state_id, is_water = state_info
            new_pixels[x, y] = SEA_COLOR if is_water else LAND_COLOR
        else:
            # Unknown state - keep black or use sea color
            new_pixels[x, y] = SEA_COLOR

print("\nStep 4: Drawing borders...")
# Second pass: detect and draw borders (only check right and down to make 1px thick)
for y in range(height):
    if y % 100 == 0:
        print(f"  Processing borders row {y}/{height}...")

    for x in range(width):
        current_color = pixels[x, y]
        current_state = color_to_state.get(current_color, (None, None))[0]

        if current_state is None:
            continue

        is_border = False

        # Only check right and down neighbors (creates 1px border instead of 2px)
        # Right
        if x + 1 < width:
            neighbor_color = pixels[x + 1, y]
            neighbor_state = color_to_state.get(neighbor_color, (None, None))[0]
            if neighbor_state != current_state:
                is_border = True

        # Down
        if y + 1 < height:
            neighbor_color = pixels[x, y + 1]
            neighbor_state = color_to_state.get(neighbor_color, (None, None))[0]
            if neighbor_state != current_state:
                is_border = True

        if is_border:
            new_pixels[x, y] = BORDER_COLOR

print(f"\nStep 5: Saving to {output_file}...")
new_img.save(output_file, 'PNG')

print("\n✓ Done! Visualization created successfully.")