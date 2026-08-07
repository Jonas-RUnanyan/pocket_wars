#!/usr/bin/env python3
"""
Find which LAND provinces aren't assigned to any state
"""

import os
import re
from pathlib import Path

def parse_definitions(definition_file):
    """Parse definition.csv to get province info including terrain type"""
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
                terrain_type = parts[4].lower()  # 'land', 'sea', 'lake'
                
                provinces[province_id] = {
                    'color': (r, g, b),
                    'type': terrain_type,
                    'is_land': terrain_type == 'land'
                }
            except (ValueError, IndexError):
                continue
    
    return provinces

def parse_state_file(state_file):
    """Parse a single state definition file"""
    try:
        with open(state_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        print(f"  Error reading {state_file}: {e}")
        return None, []
    
    # Extract state ID from filename
    filename = os.path.basename(state_file)
    state_id_match = re.match(r'(\d+)', filename)
    state_id = state_id_match.group(1) if state_id_match else "?"
    
    # Extract state name from comment
    name_match = re.search(r'name="[^"]*"\s*#\s*([^\n]+)', content)
    state_name = name_match.group(1).strip() if name_match else None
    
    if not state_name:
        state_match = re.search(r'name="(STATE_\d+)"', content)
        state_name = state_match.group(1) if state_match else f"State_{state_id}"
    
    # Extract province list
    provinces_match = re.search(r'provinces\s*=\s*\{([^}]+)\}', content)
    if not provinces_match:
        return state_name, []
    
    province_ids = []
    for x in provinces_match.group(1).split():
        try:
            province_ids.append(int(x))
        except ValueError:
            continue
    
    return state_name, province_ids

def parse_all_states(states_directory):
    """Parse all state files"""
    states = {}
    all_provinces_in_states = set()
    state_files = list(Path(states_directory).glob('*.txt'))
    
    print(f"Found {len(state_files)} state files in directory")
    
    failed_files = []
    for state_file in sorted(state_files):
        state_name, province_ids = parse_state_file(state_file)
        if state_name and province_ids:
            states[state_name] = province_ids
            all_provinces_in_states.update(province_ids)
        elif state_name:
            failed_files.append((state_file.name, state_name))
    
    if failed_files:
        print(f"\n⚠ Warning: {len(failed_files)} state files had no provinces:")
        for fname, sname in failed_files[:10]:
            print(f"  - {fname} ({sname})")
        if len(failed_files) > 10:
            print(f"  ... and {len(failed_files) - 10} more")
    
    return states, all_provinces_in_states

def main(definition_csv, states_dir):
    print("=== MISSING LAND PROVINCES ANALYSIS ===\n")
    
    print("Step 1: Loading province definitions...")
    provinces = parse_definitions(definition_csv)
    print(f"  ✓ Loaded {len(provinces)} province definitions")
    
    # Count by type
    land_count = sum(1 for p in provinces.values() if p['is_land'])
    sea_count = sum(1 for p in provinces.values() if p['type'] == 'sea')
    lake_count = sum(1 for p in provinces.values() if p['type'] == 'lake')
    other_count = len(provinces) - land_count - sea_count - lake_count
    
    print(f"    - Land provinces: {land_count}")
    print(f"    - Sea provinces: {sea_count}")
    print(f"    - Lake provinces: {lake_count}")
    print(f"    - Other: {other_count}")
    
    print("\nStep 2: Loading state definitions...")
    states, provinces_in_states = parse_all_states(states_dir)
    print(f"  ✓ Loaded {len(states)} states")
    print(f"  ✓ {len(provinces_in_states)} total provinces assigned to states")
    
    print("\nStep 3: Finding missing provinces...")
    all_province_ids = set(provinces.keys())
    missing_province_ids = all_province_ids - provinces_in_states
    
    print(f"  ✓ {len(missing_province_ids)} provinces NOT in any state")
    
    # Classify missing provinces
    missing_land = []
    missing_sea = []
    missing_lake = []
    missing_other = []
    
    for pid in missing_province_ids:
        if pid not in provinces:
            continue
        ptype = provinces[pid]['type']
        if ptype == 'land':
            missing_land.append(pid)
        elif ptype == 'sea':
            missing_sea.append(pid)
        elif ptype == 'lake':
            missing_lake.append(pid)
        else:
            missing_other.append(pid)
    
    print(f"\n  Missing by type:")
    print(f"    - Land: {len(missing_land)} ⚠ PROBLEM!")
    print(f"    - Sea: {len(missing_sea)} (expected)")
    print(f"    - Lake: {len(missing_lake)} (expected)")
    print(f"    - Other: {len(missing_other)}")
    
    if missing_land:
        print(f"\n=== MISSING LAND PROVINCES ===")
        print(f"These {len(missing_land)} LAND provinces are not assigned to any state:\n")
        
        # Show first 50
        for i, pid in enumerate(sorted(missing_land)[:50]):
            print(f"  Province {pid}: RGB{provinces[pid]['color']}")
        
        if len(missing_land) > 50:
            print(f"\n  ... and {len(missing_land) - 50} more missing land provinces")
        
        # Save to file
        output_file = "missing_land_provinces.txt"
        with open(output_file, 'w') as f:
            f.write(f"Missing Land Provinces: {len(missing_land)} total\n")
            f.write("=" * 60 + "\n\n")
            for pid in sorted(missing_land):
                color = provinces[pid]['color']
                f.write(f"Province {pid}: RGB{color}\n")
        
        print(f"\n✓ Full list saved to: {output_file}")
    
    print("\n=== DIAGNOSIS ===")
    if missing_land:
        print(f"⚠ PROBLEM CONFIRMED: {len(missing_land)} land provinces are missing from states")
        print("\nPossible causes:")
        print("1. DLC content - some provinces only exist with certain DLC")
        print("2. Mod content mixed with vanilla")
        print("3. State files from different version than provinces.bmp")
        print("4. Some provinces intentionally not in states (colonial wastelands?)")
        print("\nNext steps:")
        print("- Check if the missing provinces are in important regions")
        print("- You might need to manually create state entries for them")
        print("- Or ignore them if they're in unimportant areas")
    else:
        print("✓ All land provinces are assigned to states!")
    
    # Also check for provinces in states that don't exist
    print("\n=== REVERSE CHECK ===")
    nonexistent = provinces_in_states - all_province_ids
    if nonexistent:
        print(f"⚠ {len(nonexistent)} provinces referenced in states don't exist in definitions!")
        print(f"  First 20: {sorted(list(nonexistent))[:20]}")
    else:
        print("✓ All provinces in states exist in definitions")

if __name__ == "__main__":
    import sys

    definition_csv = "./definition.csv"
    states_dir = "./states"

    if not os.path.exists(definition_csv):
        print(f"Error: definition.csv not found: {definition_csv}")
        sys.exit(1)
    if not os.path.isdir(states_dir):
        print(f"Error: states directory not found: {states_dir}")
        sys.exit(1)
    
    main(definition_csv, states_dir)
