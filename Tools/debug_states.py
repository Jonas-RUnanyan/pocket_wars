#!/usr/bin/env python3
"""
HOI4 State Bitmap Generator - DEBUG VERSION
Helps diagnose why some provinces aren't being converted to states
"""

import os
import re
from PIL import Image
from pathlib import Path
from collections import Counter

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

def parse_state_file(state_file):
    """Parse a single state definition file to extract name and provinces"""
    with open(state_file, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # Extract state name from comment: name="STATE_1" # Corsica
    name_match = re.search(r'name="[^"]*"\s*#\s*([^\n]+)', content)
    state_name = name_match.group(1).strip() if name_match else None
    
    # If no comment name, try to extract from STATE_X
    if not state_name:
        state_match = re.search(r'name="(STATE_\d+)"', content)
        state_name = state_match.group(1) if state_match else "Unknown"
    
    # Extract province list: provinces={ 3838 9851 11804 }
    provinces_match = re.search(r'provinces\s*=\s*\{([^}]+)\}', content)
    if not provinces_match:
        return None, []
    
    province_ids = [int(x) for x in provinces_match.group(1).split()]
    
    return state_name, province_ids

def parse_all_states(states_directory):
    """Parse all state files in directory"""
    states = {}
    state_files = Path(states_directory).glob('*.txt')
    
    for state_file in sorted(state_files):
        state_name, province_ids = parse_state_file(state_file)
        if state_name and province_ids:
            states[state_name] = province_ids
    
    return states

def generate_unique_color(index):
    """Generate a unique RGB color for state index"""
    r = (index * 7) % 256
    g = (index * 13) % 256
    b = (index * 19) % 256
    return (r, g, b)

def debug_color_matching(provinces_bmp, definition_csv, states_dir):
    """Debug version - shows what's going wrong"""
    
    print("=== DEBUG MODE ===\n")
    
    print("Step 1: Loading province color definitions...")
    province_colors = parse_definitions(definition_csv)
    print(f"  ✓ Loaded {len(province_colors)} province definitions")
    
    print("\nStep 2: Loading state definitions...")
    states = parse_all_states(states_dir)
    print(f"  ✓ Loaded {len(states)} states")
    
    # Count how many provinces are in states
    all_provinces_in_states = set()
    for state_name, province_ids in states.items():
        all_provinces_in_states.update(province_ids)
    print(f"  ✓ {len(all_provinces_in_states)} unique provinces assigned to states")
    
    print("\nStep 3: Loading provinces bitmap...")
    img = Image.open(provinces_bmp)
    img = img.convert('RGB')
    pixels = img.load()
    width, height = img.size
    print(f"  ✓ Image size: {width}x{height}")
    
    print("\nStep 4: Analyzing bitmap colors...")
    # Sample pixels to see what colors are actually in the bitmap
    unique_colors_in_bitmap = set()
    sample_size = 0
    for y in range(0, height, 10):  # Sample every 10th row
        for x in range(0, width, 10):  # Sample every 10th column
            unique_colors_in_bitmap.add(pixels[x, y])
            sample_size += 1
    
    print(f"  ✓ Found {len(unique_colors_in_bitmap)} unique colors in bitmap (from {sample_size} samples)")
    
    # Create reverse lookup: RGB color -> province_id
    color_to_province = {color: pid for pid, color in province_colors.items()}
    
    # Check how many bitmap colors match definitions
    matched_colors = 0
    unmatched_colors = []
    for color in unique_colors_in_bitmap:
        if color in color_to_province:
            matched_colors += 1
        else:
            unmatched_colors.append(color)
            if len(unmatched_colors) <= 10:  # Show first 10 unmatched
                print(f"    Unmatched color in bitmap: RGB{color}")
    
    print(f"\n  ✓ Matched: {matched_colors}/{len(unique_colors_in_bitmap)} colors")
    print(f"  ✗ Unmatched: {len(unmatched_colors)} colors")
    
    if len(unmatched_colors) > 10:
        print(f"    (showing first 10, {len(unmatched_colors) - 10} more unmatched)")
    
    # Check if provinces in definitions exist in bitmap
    print("\nStep 5: Checking if definition colors exist in bitmap...")
    sample_provinces = list(province_colors.items())[:20]
    found_in_bitmap = 0
    for pid, color in sample_provinces:
        if color in unique_colors_in_bitmap:
            found_in_bitmap += 1
        else:
            print(f"    Definition color NOT in bitmap: Province {pid} = RGB{color}")
    
    print(f"  ✓ {found_in_bitmap}/20 sample definition colors found in bitmap")
    
    # Check coverage
    print("\nStep 6: Analyzing full image coverage...")
    colors_found = Counter()
    provinces_found = Counter()
    
    for y in range(0, height, 5):
        for x in range(0, width, 5):
            pixel_color = pixels[x, y]
            colors_found[pixel_color] += 1
            
            province_id = color_to_province.get(pixel_color)
            if province_id:
                provinces_found[province_id] += 1
    
    print(f"  ✓ Found {len(provinces_found)} different provinces in bitmap")
    print(f"  ✓ Found {len(colors_found)} different colors in bitmap")
    
    # Most common unmatched colors
    unmatched_in_sample = {c: count for c, count in colors_found.items() if c not in color_to_province}
    if unmatched_in_sample:
        print(f"\n  Most common UNMATCHED colors (these pixels won't convert):")
        for color, count in sorted(unmatched_in_sample.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    RGB{color}: {count} pixels")
    
    print("\n=== DIAGNOSIS ===")
    if len(unmatched_colors) > len(unique_colors_in_bitmap) * 0.5:
        print("⚠ PROBLEM: Over 50% of colors don't match definitions!")
        print("  Possible causes:")
        print("  1. Wrong definition.csv file (doesn't match this provinces.bmp)")
        print("  2. Provinces.bmp was modified/saved in wrong format")
        print("  3. Image compression artifacts")
    elif len(provinces_found) < len(all_provinces_in_states) * 0.5:
        print("⚠ PROBLEM: Many provinces from states not found in bitmap!")
        print("  Possible causes:")
        print("  1. State files don't match this map version")
        print("  2. Bitmap is from different HOI4 version/mod")
    else:
        print("✓ Color matching looks mostly OK")
        print(f"  {len(provinces_found)} provinces detected")
        print(f"  {len(all_provinces_in_states)} provinces in state definitions")
    
    print("\n=== RECOMMENDATIONS ===")
    print("1. Make sure provinces.bmp and definition.csv are from the SAME HOI4 installation")
    print("2. If you edited provinces.bmp, save it as PNG (not JPG) to avoid compression")
    print("3. Make sure state files match your HOI4 version")

if __name__ == "__main__":
    import sys

    provinces_bmp = "./provinces.bmp"
    definition_csv = "./definition.csv"
    states_dir = "./states"

    if not os.path.exists(provinces_bmp):
        print(f"Error: provinces.bmp not found: {provinces_bmp}")
        sys.exit(1)
    if not os.path.exists(definition_csv):
        print(f"Error: definition.csv not found: {definition_csv}")
        sys.exit(1)
    if not os.path.isdir(states_dir):
        print(f"Error: states directory not found: {states_dir}")
        sys.exit(1)
    
    debug_color_matching(provinces_bmp, definition_csv, states_dir)
