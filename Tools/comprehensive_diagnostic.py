#!/usr/bin/env python3
"""
Comprehensive diagnostic - find parsing bugs
"""

import os
import re
from pathlib import Path

def parse_definitions(definition_file):
    """Parse definition.csv"""
    provinces = {}
    
    with open(definition_file, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split(';')
            if len(parts) < 5:
                continue
            
            try:
                province_id = int(parts[0])
                r = int(parts[1])
                g = int(parts[2])
                b = int(parts[3])
                terrain_type = parts[4].lower()
                
                provinces[province_id] = {
                    'color': (r, g, b),
                    'type': terrain_type
                }
            except (ValueError, IndexError):
                continue
    
    return provinces

def parse_state_file_verbose(state_file):
    """Parse with verbose output to see what's happening"""
    filename = os.path.basename(state_file)
    
    try:
        with open(state_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        return filename, None, [], f"Read error: {e}"
    
    # Extract state name
    name_match = re.search(r'name="[^"]*"\s*#\s*([^\n]+)', content)
    state_name = name_match.group(1).strip() if name_match else None
    
    if not state_name:
        state_match = re.search(r'name="(STATE_\d+)"', content)
        state_name = state_match.group(1) if state_match else "Unknown"
    
    # Extract province list - try multiple patterns
    province_ids = []
    
    # Pattern 1: provinces={ ... }
    provinces_match = re.search(r'provinces\s*=\s*\{([^}]+)\}', content, re.DOTALL)
    if provinces_match:
        province_text = provinces_match.group(1)
        for word in province_text.split():
            try:
                province_ids.append(int(word))
            except ValueError:
                continue
    
    status = "OK" if province_ids else "NO PROVINCES FOUND"
    
    return filename, state_name, province_ids, status

def main(definition_csv, states_dir):
    print("=== COMPREHENSIVE DIAGNOSTIC ===\n")
    
    print("Step 1: Loading definitions...")
    provinces_def = parse_definitions(definition_csv)
    land_provinces = {pid for pid, data in provinces_def.items() if data['type'] == 'land'}
    print(f"  Total provinces: {len(provinces_def)}")
    print(f"  Land provinces: {len(land_provinces)}")
    
    print("\nStep 2: Parsing state files with verbose output...")
    state_files = list(Path(states_dir).glob('*.txt'))
    print(f"  Found {len(state_files)} state files\n")
    
    all_provinces_in_states = set()
    states_with_no_provinces = []
    states_parsed = 0
    
    # Parse first 10 to see format
    print("  Sampling first 10 state files:")
    for i, state_file in enumerate(sorted(state_files)[:10]):
        fname, sname, pids, status = parse_state_file_verbose(state_file)
        print(f"    {fname}: {sname} - {len(pids)} provinces - {status}")
        if pids:
            all_provinces_in_states.update(pids)
            states_parsed += 1
        else:
            states_with_no_provinces.append(fname)
    
    # Parse the rest silently
    print(f"\n  Parsing remaining {len(state_files) - 10} files...")
    for state_file in sorted(state_files)[10:]:
        fname, sname, pids, status = parse_state_file_verbose(state_file)
        if pids:
            all_provinces_in_states.update(pids)
            states_parsed += 1
        else:
            states_with_no_provinces.append(fname)
    
    print(f"\n  Results:")
    print(f"    ✓ Successfully parsed: {states_parsed} states")
    print(f"    ✗ No provinces found: {len(states_with_no_provinces)} states")
    print(f"    ✓ Total unique provinces in states: {len(all_provinces_in_states)}")
    
    if states_with_no_provinces:
        print(f"\n  Files with no provinces (first 20):")
        for fname in states_with_no_provinces[:20]:
            print(f"    - {fname}")
    
    print("\nStep 3: Analyzing coverage...")
    
    # Total provinces not in states
    all_province_ids = set(provinces_def.keys())
    missing = all_province_ids - all_provinces_in_states
    
    print(f"  Total provinces in definitions: {len(all_province_ids)}")
    print(f"  Provinces assigned to states: {len(all_provinces_in_states)}")
    print(f"  Provinces NOT in states: {len(missing)}")
    
    # Break down by type
    missing_land = {pid for pid in missing if provinces_def.get(pid, {}).get('type') == 'land'}
    missing_sea = {pid for pid in missing if provinces_def.get(pid, {}).get('type') == 'sea'}
    missing_lake = {pid for pid in missing if provinces_def.get(pid, {}).get('type') == 'lake'}
    
    print(f"\n  Missing breakdown:")
    print(f"    Land: {len(missing_land)}")
    print(f"    Sea: {len(missing_sea)}")
    print(f"    Lake: {len(missing_lake)}")
    print(f"    Other: {len(missing) - len(missing_land) - len(missing_sea) - len(missing_lake)}")
    
    # Check which land provinces are missing
    if missing_land:
        print(f"\n=== MISSING LAND PROVINCES ===")
        print(f"  {len(missing_land)} land provinces not in any state")
        print(f"\n  First 30 missing land province IDs:")
        for pid in sorted(missing_land)[:30]:
            print(f"    Province {pid}")
        
        if len(missing_land) > 30:
            print(f"    ... and {len(missing_land) - 30} more")
    
    # Check for provinces in states that don't exist in definitions
    print("\n=== REVERSE CHECK ===")
    invalid_provinces = all_provinces_in_states - all_province_ids
    if invalid_provinces:
        print(f"  ⚠ {len(invalid_provinces)} provinces in states don't exist in definitions!")
        print(f"  First 30: {sorted(list(invalid_provinces))[:30]}")
    else:
        print(f"  ✓ All provinces in states exist in definitions")
    
    # Sample a problematic state file if exists
    if states_with_no_provinces:
        print("\n=== SAMPLE PROBLEMATIC FILE ===")
        problem_file = Path(states_dir) / states_with_no_provinces[0]
        print(f"  File: {states_with_no_provinces[0]}")
        print(f"  First 500 characters:")
        with open(problem_file, 'r', encoding='utf-8-sig') as f:
            content = f.read(500)
            print("  " + content[:500].replace('\n', '\n  '))

if __name__ == "__main__":
    import sys

    definition_csv = "./definition.csv"
    states_dir = "./states"

    if not os.path.exists(definition_csv):
        print(f"Error: {definition_csv} not found")
        sys.exit(1)
    if not os.path.isdir(states_dir):
        print(f"Error: {states_dir} not found")
        sys.exit(1)
    
    main(definition_csv, states_dir)
