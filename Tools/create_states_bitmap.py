#!/usr/bin/env python3
"""
HOI4 State Bitmap Generator
Converts provinces.bmp into states.bmp by merging provinces into states
Also generates:
- Adjacencies CSV (which states border each other)
- Colors CSV (maps RGB colors to state IDs and names)
"""

import os
import re
from PIL import Image
from pathlib import Path


def parse_localization_file(loc_file):
    """Parse HOI4 localization YAML file to get STATE_X -> name mapping"""
    state_names = {}

    with open(loc_file, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()

            # Match pattern: STATE_123:0 "Name" or STATE_123: "Name"
            match = re.match(r'STATE_(\d+):\d*\s+"([^"]+)"', line)
            if match:
                state_num = int(match.group(1))
                state_name = match.group(2)
                state_key = f"STATE_{state_num}"
                state_names[state_key] = state_name

    return state_names


def parse_definitions(definition_file):
    """Parse definition.csv to get province_id -> (R, G, B) mapping"""
    province_colors = {}

    with open(definition_file, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split(';')
            if len(parts) < 4:
                continue

            try:
                province_id = int(parts[0])
                r = int(parts[1])
                g = int(parts[2])
                b = int(parts[3])
                province_colors[province_id] = (r, g, b)
            except ValueError:
                continue

    return province_colors


def parse_state_file(state_file, loc_names):
    """Parse a single state definition file to extract name and provinces"""
    with open(state_file, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    # Use filename as unique identifier (e.g., "58-Schleswig_-_Holstein.txt")
    filename = os.path.basename(state_file)

    # Extract the exact name value from name = "..." (note: spaces around =)
    name_match = re.search(r'name\s*=\s*"([^"]+)"', content)
    name_key = name_match.group(1) if name_match else None

    # Look up the localized name using the exact name from the file
    if name_key and name_key in loc_names:
        state_name = loc_names[name_key]
    else:
        # Fallback: try to get from comment
        comment_match = re.search(r'name\s*=\s*"[^"]*"\s*#\s*([^\n]+)', content)
        state_name = comment_match.group(1).strip() if comment_match else (name_key if name_key else "Unknown")

    # Extract province list: provinces={ 3838 9851 11804 }
    # Use re.DOTALL to handle multi-line province lists
    provinces_match = re.search(r'provinces\s*=\s*\{([^}]+)\}', content, re.DOTALL)
    if not provinces_match:
        return None, None, []

    # Parse each word as potential province ID, skip non-integers
    province_ids = []
    for word in provinces_match.group(1).split():
        try:
            province_ids.append(int(word))
        except ValueError:
            continue

    return filename, state_name, province_ids


def parse_all_states(states_directory, loc_names):
    """Parse all state files in directory"""
    states = {}  # filename -> (state_name, province_ids)
    state_files = Path(states_directory).glob('*.txt')

    files_parsed = 0
    files_failed = 0

    for state_file in sorted(state_files):
        filename, state_name, province_ids = parse_state_file(state_file, loc_names)
        if filename and province_ids:
            states[filename] = (state_name, province_ids)
            files_parsed += 1
        else:
            files_failed += 1

    print(f"  Successfully parsed: {files_parsed} states")
    if files_failed > 0:
        print(f"  Failed to parse: {files_failed} files (no provinces found)")

    return states


def generate_unique_color(index):
    """Generate a unique RGB15 color for state index"""
    # Work directly in RGB15 space (5 bits per channel = 0-31)
    # Total possible colors: 32 * 32 * 32 = 32768

    if index >= 32768:
        raise ValueError(f"Cannot generate more than 32768 unique RGB15 colors (got index {index})")

    # Treat index as a 15-bit number: RRRRR GGGGG BBBBB
    r5 = (index >> 10) & 0x1F  # Top 5 bits
    g5 = (index >> 5) & 0x1F  # Middle 5 bits
    b5 = index & 0x1F  # Bottom 5 bits

    # Convert to 8-bit RGB for the bitmap (scale 0-31 to 0-255)
    r8 = (r5 << 3) | (r5 >> 2)  # Replicate bits for better distribution
    g8 = (g5 << 3) | (g5 >> 2)
    b8 = (b5 << 3) | (b5 >> 2)

    return (r8, g8, b8)


def detect_state_adjacencies(img, color_to_province, province_to_state_id):
    """
    Detect which states are adjacent by scanning the bitmap
    Returns dict: state_id -> set of adjacent state_ids
    """
    print("\n  Detecting state adjacencies...")
    width, height = img.size
    pixels = img.load()

    adjacencies = {}  # state_id -> set of adjacent state_ids

    # Scan image to find adjacent pixels with different colors
    for y in range(height):
        if y % 200 == 0:
            print(f"    Scanning row {y}/{height}...")

        for x in range(width):
            current_color = pixels[x, y]
            current_province = color_to_province.get(current_color)

            if current_province is None:
                continue

            current_state = province_to_state_id.get(current_province)
            if current_state is None:
                continue

            # Initialize set for this state if needed
            if current_state not in adjacencies:
                adjacencies[current_state] = set()

            # Check all 4 directions (sets handle duplicates automatically)
            neighbors = []

            # Right
            if x + 1 < width:
                neighbors.append(pixels[x + 1, y])

            # Left
            if x - 1 >= 0:
                neighbors.append(pixels[x - 1, y])

            # Down
            if y + 1 < height:
                neighbors.append(pixels[x, y + 1])

            # Up
            if y - 1 >= 0:
                neighbors.append(pixels[x, y - 1])

            # Check each neighbor
            for neighbor_color in neighbors:
                neighbor_province = color_to_province.get(neighbor_color)
                if neighbor_province:
                    neighbor_state = province_to_state_id.get(neighbor_province)
                    if neighbor_state and neighbor_state != current_state:
                        # States are adjacent - set automatically handles duplicates
                        adjacencies[current_state].add(neighbor_state)

    print(f"    ✓ Found adjacencies for {len(adjacencies)} states")
    return adjacencies


def save_adjacencies_csv(adjacencies, state_id_to_name, output_file):
    """Save state adjacencies to CSV file"""
    print(f"\n  Saving adjacencies to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("StateID,AdjacentStateIDs\n")

        for state_id in sorted(adjacencies.keys()):
            adjacent_ids = sorted(adjacencies[state_id])

            # Format as semicolon-separated list of IDs
            adjacent_ids_str = ";".join(str(aid) for aid in adjacent_ids)

            f.write(f'{state_id},{adjacent_ids_str}\n')

    print(f"    ✓ Saved {len(adjacencies)} states with adjacencies")


def save_color_mapping_csv(state_colors, state_id_to_name, output_file):
    """Save color to state ID and name mapping"""
    print(f"\n  Saving color mapping to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("StateID,R,G,B,Filename,StateName\n")

        for state_id in sorted(state_colors.keys()):
            color = state_colors[state_id]
            filename, state_name = state_id_to_name.get(state_id, ("Unknown", "Unknown"))
            r, g, b = color
            f.write(f'{state_id},{r},{g},{b},"{filename}","{state_name}"\n')

    print(f"    ✓ Saved {len(state_colors)} state color mappings")


def create_state_bitmap(provinces_bmp, definition_csv, states_dir, loc_file, output_file):
    """Main function to create state bitmap"""

    print("Step 1: Loading province color definitions...")
    province_colors = parse_definitions(definition_csv)
    print(f"  Loaded {len(province_colors)} province definitions")

    print("\nStep 2: Loading state name localization...")
    loc_names = parse_localization_file(loc_file)
    print(f"  Loaded {len(loc_names)} state name translations")

    print("\nStep 3: Loading state definitions...")
    states = parse_all_states(states_dir, loc_names)
    print(f"  Loaded {len(states)} states")

    print("\nStep 4: Loading provinces bitmap...")
    img = Image.open(provinces_bmp)
    img = img.convert('RGB')
    pixels = img.load()
    width, height = img.size
    print(f"  Image size: {width}x{height}")

    print("\nStep 5: Creating color lookup tables...")
    # Create reverse lookup: RGB color -> province_id
    color_to_province = {color: pid for pid, color in province_colors.items()}

    # Assign numeric IDs to states and create lookup tables
    province_to_state_color = {}
    province_to_state_id = {}
    state_colors = {}  # numeric_id -> color
    state_id_to_name = {}  # numeric_id -> (filename, state_name)

    for state_idx, (filename, (state_name, province_ids)) in enumerate(states.items()):
        numeric_id = state_idx + 1  # Start IDs from 1
        state_color = generate_unique_color(numeric_id)  # Use numeric_id so we skip (0,0,0)

        state_colors[numeric_id] = state_color
        state_id_to_name[numeric_id] = (filename, state_name)  # Just use state_name as-is

        for province_id in province_ids:
            province_to_state_color[province_id] = state_color
            province_to_state_id[province_id] = numeric_id

    print("\nStep 6: Converting provinces to states...")
    new_img = Image.new('RGB', (width, height), (0, 0, 0))
    new_pixels = new_img.load()

    provinces_not_found = set()
    pixels_converted = 0

    for y in range(height):
        if y % 100 == 0:
            print(f"  Processing row {y}/{height}...")

        for x in range(width):
            pixel_color = pixels[x, y]

            # Find which province this pixel belongs to
            province_id = color_to_province.get(pixel_color)

            if province_id is not None:
                # Find which state this province belongs to
                state_color = province_to_state_color.get(province_id)

                if state_color:
                    new_pixels[x, y] = state_color
                    pixels_converted += 1
                else:
                    # Province not assigned to any state - keep original or mark
                    new_pixels[x, y] = pixel_color
                    provinces_not_found.add(province_id)
            else:
                # Unknown color - probably ocean/lakes - keep original
                new_pixels[x, y] = pixel_color

    print(f"\n  Converted {pixels_converted} pixels")
    if provinces_not_found:
        print(f"  Warning: {len(provinces_not_found)} provinces not assigned to states")

    print(f"\nStep 7: Saving output to {output_file}...")
    new_img.save(output_file, 'PNG')

    # Generate output filenames based on the bitmap output file
    base_path = os.path.splitext(output_file)[0]
    adjacencies_file = base_path + "_adjacencies.csv"
    colors_file = base_path + "_colors.csv"

    print("\nStep 8: Detecting state adjacencies...")
    adjacencies = detect_state_adjacencies(img, color_to_province, province_to_state_id)
    save_adjacencies_csv(adjacencies, state_id_to_name, adjacencies_file)

    print("\nStep 9: Saving color mappings...")
    save_color_mapping_csv(state_colors, state_id_to_name, colors_file)

    print("\n✓ Done! State bitmap and data files created successfully.")
    print(f"  Total states: {len(states)}")
    print(f"  Output files:")
    print(f"    - Bitmap: {output_file}")
    print(f"    - Adjacencies: {adjacencies_file}")
    print(f"    - Colors: {colors_file}")


if __name__ == "__main__":
    import sys

    provinces_bmp = "./provinces.bmp"
    definition_csv = "./definition.csv"
    states_dir = "./states"
    loc_file="state_names_l_english.yml"
    output_file = "./states.bmp"

    # Verify files exist
    if not os.path.exists(provinces_bmp):
        print(f"Error: provinces.bmp not found: {provinces_bmp}")
        sys.exit(1)
    if not os.path.exists(definition_csv):
        print(f"Error: definition.csv not found: {definition_csv}")
        sys.exit(1)
    if not os.path.isdir(states_dir):
        print(f"Error: states directory not found: {states_dir}")
        sys.exit(1)
    if not os.path.exists(loc_file):
        print(f"Error: localization file not found: {loc_file}")
        sys.exit(1)

    create_state_bitmap(provinces_bmp, definition_csv, states_dir, loc_file, output_file)