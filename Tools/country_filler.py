import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw
import csv
import json
import re

# Sentinel values
UNOWNED  = 0xFF    # province_owners: no owner
NO_CAP   = 0xFFFF  # country capital: not set


class ProvinceMapEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Province Owner Editor")

        # Data structures
        self.province_map_img = None
        self.province_colors = {}
        self.province_id_to_color = {}
        self.province_names = {}
        self.province_is_water = {}

        self.countries = {}
        self.next_country_id = 0
        self.province_owners = {}
        self.province_cores = {}

        self.active_country_id = None
        self.display_img = None
        self.photo = None

        self.mode = tk.StringVar(value='ownership')

        # Zoom and pan state
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        self.setup_gui()

    # ------------------------------------------------------------------
    # PROVINCE DATA PARSER
    # ------------------------------------------------------------------

    def parse_province_data_c(self, filepath):
        provinces = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        match = re.search(r'Province\s+provinces\[.*?\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
        if not match:
            raise ValueError("Could not find provinces array in province_data.c")

        array_content = match.group(1)
        # Handles any number of trailing fields (owner, is_water, center_x, center_y, ...)
        pattern = r'\{\s*"([^"]+)"\s*,\s*0x([0-9A-Fa-f]+)\s*,\s*\d+\s*,\s*(\d+)(?:,\s*\d+)*\s*\}'
        matches = re.findall(pattern, array_content)

        province_id = 0
        for name, color_hex, is_water in matches:
            # Color stored as full RGB24 — extract channels directly
            rgb24_int = int(color_hex, 16)
            rgb24 = ((rgb24_int >> 16) & 0xFF, (rgb24_int >> 8) & 0xFF, rgb24_int & 0xFF)
            provinces[province_id] = {
                'name':     name,
                'color':    rgb24,
                'is_water': int(is_water)
            }
            province_id += 1

        return provinces

    # ------------------------------------------------------------------
    # GUI SETUP
    # ------------------------------------------------------------------

    def setup_gui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel
        left_panel = ttk.Frame(main_frame, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)

        ttk.Label(left_panel, text="Countries", font=('Arial', 12, 'bold')).pack(pady=5)

        # Mode selector
        mode_frame = ttk.LabelFrame(left_panel, text="Mode", padding=5)
        mode_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(mode_frame, text="Ownership",  variable=self.mode,
                        value='ownership', command=self.on_mode_change).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Core States", variable=self.mode,
                        value='cores',    command=self.on_mode_change).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Capital",    variable=self.mode,
                        value='capital',  command=self.on_mode_change).pack(anchor=tk.W)

        # Country list
        self.country_listbox = tk.Listbox(left_panel, height=15)
        self.country_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.country_listbox.bind('<<ListboxSelect>>', self.on_country_select)

        # Buttons
        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Add Country",    command=self.add_country).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Edit Country",   command=self.edit_country).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Delete Country", command=self.delete_country).pack(fill=tk.X, pady=2)

        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)

        ttk.Button(left_panel, text="Load Map",     command=self.load_map).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Export to C",  command=self.export_to_c).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Save Project", command=self.save_project).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Load Project", command=self.load_project).pack(fill=tk.X, pady=2)

        # Zoom controls
        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(left_panel, text="Zoom Controls", font=('Arial', 10, 'bold')).pack(pady=5)
        ttk.Button(left_panel, text="Reset View", command=self.reset_view).pack(fill=tk.X, pady=2)
        self.zoom_label = ttk.Label(left_panel, text="Zoom: 100%")
        self.zoom_label.pack(pady=2)

        # Right panel
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(right_panel, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Button-1>',        self.on_canvas_click)
        self.canvas.bind('<B1-Motion>',       self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        self.canvas.bind('<MouseWheel>',      self.on_mouse_wheel)
        self.canvas.bind('<Button-4>',        self.on_mouse_wheel)
        self.canvas.bind('<Button-5>',        self.on_mouse_wheel)

        self.status_label = ttk.Label(self.root, text="Ready. Load a map to begin.", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # MODE
    # ------------------------------------------------------------------

    def on_mode_change(self):
        self.update_display()
        if self.active_country_id is not None:
            country = self.countries[self.active_country_id]
            mode = self.mode.get()
            hint = {
                'ownership': "click to assign/unassign ownership",
                'cores':     "click to add/remove cores",
                'capital':   "click an owned province to set as capital",
            }.get(mode, "")
            self.status_label.config(text=f"Active: {country['name']} — {hint}")

    # ------------------------------------------------------------------
    # MAP LOADING
    # ------------------------------------------------------------------

    def load_map(self):
        from tkinter import filedialog

        province_data_file = filedialog.askopenfilename(
            title="Select province_data.c",
            filetypes=[("C source files", "*.c"), ("All files", "*.*")]
        )
        if not province_data_file:
            return

        map_file = filedialog.askopenfilename(
            title="Select Province Map",
            filetypes=[("Image files", "*.png *.bmp"), ("All files", "*.*")]
        )
        if not map_file:
            return

        try:
            parsed_provinces = self.parse_province_data_c(province_data_file)

            self.province_map_img = Image.open(map_file).convert('RGB')
            pixels = self.province_map_img.load()
            width, height = self.province_map_img.size

            colors_in_map = set()
            for y in range(height):
                for x in range(width):
                    colors_in_map.add(pixels[x, y])

            self.province_colors      = {}
            self.province_id_to_color = {}
            self.province_names       = {}
            self.province_is_water    = {}

            provinces_found   = 0
            provinces_skipped = 0

            for province_id, data in parsed_provinces.items():
                color = data['color']
                if color in colors_in_map:
                    self.province_colors[color]            = province_id
                    self.province_id_to_color[province_id] = color
                    self.province_names[province_id]       = data['name']
                    self.province_is_water[province_id]    = data['is_water']

                    if province_id not in self.province_owners:
                        self.province_owners[province_id] = UNOWNED
                    if province_id not in self.province_cores:
                        self.province_cores[province_id] = set()

                    provinces_found += 1
                else:
                    provinces_skipped += 1

            # Purge stale data for provinces not in this map
            valid_ids = set(self.province_id_to_color.keys())
            for pid in [p for p in list(self.province_owners) if p not in valid_ids]:
                del self.province_owners[pid]
            for pid in [p for p in list(self.province_cores) if p not in valid_ids]:
                del self.province_cores[pid]

            self.reset_view()

            status_msg = f"Loaded {provinces_found} provinces from map"
            if provinces_skipped > 0:
                status_msg += f" (skipped {provinces_skipped} not in map)"
            self.status_label.config(text=status_msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load map: {e}")

    # ------------------------------------------------------------------
    # VIEW
    # ------------------------------------------------------------------

    def reset_view(self):
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update_display()
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_level * 100)}%")

    def on_mouse_wheel(self, event):
        if self.province_map_img is None:
            return

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        zoom_factor = 0.9 if (event.num == 5 or event.delta < 0) else 1.1
        old_zoom    = self.zoom_level
        self.zoom_level = max(0.1, min(10.0, self.zoom_level * zoom_factor))

        change  = self.zoom_level / old_zoom
        self.pan_x = canvas_x - (canvas_x - self.pan_x) * change
        self.pan_y = canvas_y - (canvas_y - self.pan_y) * change

        self.update_display()
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_level * 100)}%")

    # ------------------------------------------------------------------
    # CANVAS INPUT
    # ------------------------------------------------------------------

    def on_canvas_click(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = False

    def on_canvas_drag(self, event):
        if abs(event.x - self.drag_start_x) > 5 or abs(event.y - self.drag_start_y) > 5:
            self.is_dragging = True

        if self.is_dragging:
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            self.pan_x += dx
            self.pan_y += dy
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.update_display()

    def on_canvas_release(self, event):
        if not self.is_dragging:
            self.select_province_at(event.x, event.y)
        self.is_dragging = False

    def select_province_at(self, canvas_x, canvas_y):
        if self.province_map_img is None:
            return
        if self.active_country_id is None:
            messagebox.showwarning("No Country Selected", "Select a country first!")
            return

        x = int((canvas_x - self.pan_x) / self.zoom_level)
        y = int((canvas_y - self.pan_y) / self.zoom_level)

        width, height = self.province_map_img.size
        if x < 0 or x >= width or y < 0 or y >= height:
            return

        pixels      = self.province_map_img.load()
        color       = pixels[x, y]
        province_id = self.province_colors.get(color)

        if province_id is None:
            return

        province_name = self.province_names.get(province_id, f"Province {province_id}")
        country       = self.countries[self.active_country_id]
        country_name  = country['name']
        is_water      = self.province_is_water.get(province_id, 0)
        mode          = self.mode.get()

        if mode == 'ownership':
            if is_water:
                self.status_label.config(text=f"{province_name} is water — cannot assign ownership")
                return

            current_owner = self.province_owners.get(province_id, UNOWNED)

            if current_owner == self.active_country_id:
                self.province_owners[province_id] = UNOWNED
                # If this was the capital, clear it
                if country.get('capital') == province_id:
                    country['capital'] = NO_CAP
                self.status_label.config(text=f"Unassigned {province_name} from {country_name}")
            elif current_owner == UNOWNED:
                self.province_owners[province_id] = self.active_country_id
                self.status_label.config(text=f"Assigned {province_name} to {country_name}")
            else:
                other = self.countries[current_owner]['name']
                self.status_label.config(text=f"{province_name} is owned by {other}")
                return

        elif mode == 'cores':
            cores = self.province_cores.get(province_id, set())
            if self.active_country_id in cores:
                cores.discard(self.active_country_id)
                self.status_label.config(text=f"Removed {province_name} as core of {country_name}")
            else:
                cores.add(self.active_country_id)
                self.status_label.config(text=f"Added {province_name} as core of {country_name}")
            self.province_cores[province_id] = cores

        elif mode == 'capital':
            current_owner = self.province_owners.get(province_id, UNOWNED)
            if current_owner != self.active_country_id:
                self.status_label.config(
                    text=f"{province_name} is not owned by {country_name} — cannot set as capital")
                return

            if country.get('capital') == province_id:
                country['capital'] = NO_CAP
                self.status_label.config(text=f"Cleared capital of {country_name}")
            else:
                country['capital'] = province_id
                self.status_label.config(text=f"Set {province_name} as capital of {country_name}")

        self.refresh_country_list()
        self.update_display()

    # ------------------------------------------------------------------
    # DISPLAY
    # ------------------------------------------------------------------

    def update_display(self):
        if self.province_map_img is None:
            return

        display        = Image.new('RGB', self.province_map_img.size)
        pixels         = self.province_map_img.load()
        display_pixels = display.load()
        width, height  = self.province_map_img.size
        mode           = self.mode.get()

        capital_province = None
        if mode == 'capital' and self.active_country_id is not None:
            cap = self.countries[self.active_country_id].get('capital', NO_CAP)
            if cap != NO_CAP:
                capital_province = cap

        for y in range(height):
            for x in range(width):
                color       = pixels[x, y]
                province_id = self.province_colors.get(color)

                if province_id is None:
                    display_pixels[x, y] = (0, 0, 0)
                    continue

                if mode == 'ownership':
                    owner_id = self.province_owners.get(province_id, UNOWNED)
                    if owner_id == UNOWNED:
                        display_pixels[x, y] = (100, 100, 100)
                    else:
                        c = self.countries.get(owner_id)
                        display_pixels[x, y] = c['color'] if c else (100, 100, 100)

                elif mode == 'cores':
                    if self.active_country_id is not None:
                        cores = self.province_cores.get(province_id, set())
                        if self.active_country_id in cores:
                            c = self.countries.get(self.active_country_id)
                            display_pixels[x, y] = c['color'] if c else (100, 100, 100)
                        else:
                            display_pixels[x, y] = (100, 100, 100)
                    else:
                        display_pixels[x, y] = (100, 100, 100)

                elif mode == 'capital':
                    if self.active_country_id is not None:
                        owner_id = self.province_owners.get(province_id, UNOWNED)
                        if owner_id == self.active_country_id:
                            if province_id == capital_province:
                                display_pixels[x, y] = (255, 220, 0)  # bright yellow = capital
                            else:
                                c = self.countries.get(self.active_country_id)
                                display_pixels[x, y] = c['color'] if c else (100, 100, 100)
                        else:
                            display_pixels[x, y] = (60, 60, 60)
                    else:
                        display_pixels[x, y] = (100, 100, 100)

        zoomed_w = int(width  * self.zoom_level)
        zoomed_h = int(height * self.zoom_level)
        zoomed   = display.resize((zoomed_w, zoomed_h), Image.NEAREST)

        self.display_img = zoomed
        self.photo       = ImageTk.PhotoImage(zoomed)
        self.canvas.delete("all")
        self.canvas.create_image(self.pan_x, self.pan_y, anchor=tk.NW, image=self.photo)

    # ------------------------------------------------------------------
    # COUNTRY CRUD
    # ------------------------------------------------------------------

    def add_country(self):
        name = simpledialog.askstring("Add Country", "Enter country name:")
        if not name:
            return

        color = colorchooser.askcolor(title="Choose country color")
        if not color[0]:
            return

        rgb        = tuple(int(c) for c in color[0])
        country_id = self.next_country_id
        self.next_country_id += 1

        self.countries[country_id] = {
            'name':      name,
            'color':     rgb,
            'provinces': set(),
            'capital':   NO_CAP,
        }

        self.refresh_country_list()
        self.status_label.config(text=f"Added country: {name}")

    def edit_country(self):
        selection = self.country_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a country to edit")
            return

        country_id = list(self.countries.keys())[selection[0]]
        country    = self.countries[country_id]

        new_name = simpledialog.askstring("Edit Country", "Enter new name:", initialvalue=country['name'])
        if new_name:
            country['name'] = new_name

        color = colorchooser.askcolor(title="Choose new color", initialcolor=country['color'])
        if color[0]:
            country['color'] = tuple(int(c) for c in color[0])

        self.refresh_country_list()
        self.update_display()

    def delete_country(self):
        selection = self.country_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a country to delete")
            return

        country_id = list(self.countries.keys())[selection[0]]
        country    = self.countries[country_id]

        if messagebox.askyesno("Confirm Delete", f"Delete {country['name']}?"):
            for pid, owner_id in list(self.province_owners.items()):
                if owner_id == country_id:
                    self.province_owners[pid] = UNOWNED

            for pid, cores in self.province_cores.items():
                cores.discard(country_id)

            del self.countries[country_id]
            self.refresh_country_list()
            self.update_display()

    def on_country_select(self, event):
        selection = self.country_listbox.curselection()
        if selection:
            self.active_country_id = list(self.countries.keys())[selection[0]]
            country = self.countries[self.active_country_id]
            mode    = self.mode.get()
            hint = {
                'ownership': "click to assign/unassign ownership",
                'cores':     "click to add/remove cores",
                'capital':   "click an owned province to set as capital",
            }.get(mode, "")
            self.status_label.config(text=f"Active: {country['name']} — {hint}")

            if mode in ('cores', 'capital'):
                self.update_display()

    def refresh_country_list(self):
        self.country_listbox.delete(0, tk.END)
        for country_id, country in self.countries.items():
            province_count = sum(1 for o in self.province_owners.values() if o == country_id)
            core_count     = sum(1 for c in self.province_cores.values()  if country_id in c)
            cap            = country.get('capital', NO_CAP)
            cap_str        = ""
            if cap != NO_CAP:
                cap_name = self.province_names.get(cap, f"#{cap}")
                cap_str  = f" ★{cap_name}"
            self.country_listbox.insert(
                tk.END, f"{country['name']} ({province_count}P / {core_count}C){cap_str}")

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def export_to_c(self):
        from tkinter import filedialog

        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return

        try:
            valid_province_ids = set(self.province_id_to_color.keys())

            # Filter + fix owners
            valid_owners          = {}
            water_ownership_fixed = 0
            for pid, owner in self.province_owners.items():
                if pid in valid_province_ids:
                    is_water = self.province_is_water.get(pid, 0)
                    if is_water and owner != UNOWNED:
                        valid_owners[pid] = UNOWNED
                        water_ownership_fixed += 1
                    else:
                        valid_owners[pid] = owner

            # Filter cores
            valid_cores = {pid: cores for pid, cores in self.province_cores.items()
                           if pid in valid_province_ids}

            # Build stable 0-based mapping: internal id -> export index
            sorted_ids       = sorted(self.countries.keys())
            country_id_remap = {old: new for new, old in enumerate(sorted_ids)}

            # ---- countries.h ----
            with open(f"{output_dir}/countries.h", 'w', encoding='utf-8') as f:
                f.write("#ifndef COUNTRIES_H\n")
                f.write("#define COUNTRIES_H\n\n")
                f.write("typedef struct {\n")
                f.write("    const char*    name;\n")
                f.write("    unsigned short color;\n")
                f.write("    unsigned short capital;\n")
                f.write("} Country;\n\n")
                f.write(f"#define COUNTRY_COUNT {len(self.countries)}\n")
                f.write("#define NO_CAPITAL    0xFFFF\n\n")
                f.write("extern const Country countries[COUNTRY_COUNT];\n\n")
                f.write("#endif\n")

            # ---- countries.c ----
            with open(f"{output_dir}/countries.c", 'w', encoding='utf-8') as f:
                f.write("#include \"countries.h\"\n\n")
                f.write("const Country countries[COUNTRY_COUNT] = {\n")

                for i, old_id in enumerate(sorted_ids):
                    country = self.countries[old_id]
                    r, g, b = country['color']
                    r5 = r >> 3;  g5 = g >> 3;  b5 = b >> 3
                    bgr15 = 0x8000 | (b5 << 10) | (g5 << 5) | r5

                    cap = country.get('capital', NO_CAP)
                    # Validate: capital must still be owned by this country
                    if cap != NO_CAP and valid_owners.get(cap, UNOWNED) != old_id:
                        cap = NO_CAP

                    cap_str = f"0x{cap:04X}"
                    comma   = ',' if i < len(self.countries) - 1 else ''
                    f.write(f'    {{"{country["name"]}", 0x{bgr15:04X}, {cap_str}}}{comma}\n')

                f.write("};\n")

            # ---- province_owners.h ----
            max_province_id = max(valid_province_ids) if valid_province_ids else 0

            with open(f"{output_dir}/province_owners.h", 'w') as f:
                f.write("#ifndef PROVINCE_OWNERS_H\n")
                f.write("#define PROVINCE_OWNERS_H\n\n")
                f.write(f"#define PROVINCE_OWNER_COUNT {max_province_id + 1}\n")
                f.write("#define PROVINCE_UNOWNED      0xFF\n\n")
                f.write("extern unsigned char province_owners[PROVINCE_OWNER_COUNT];\n\n")
                f.write("#endif\n")

            # ---- province_owners.c ----
            with open(f"{output_dir}/province_owners.c", 'w') as f:
                f.write("#include \"province_owners.h\"\n\n")
                f.write("unsigned char province_owners[PROVINCE_OWNER_COUNT] = {\n")

                for i in range(max_province_id + 1):
                    raw_owner = valid_owners.get(i, UNOWNED)
                    owner     = 0xFF if raw_owner == UNOWNED else country_id_remap.get(raw_owner, 0xFF)
                    comma     = ',' if i < max_province_id else ''

                    if i % 16 == 0:
                        f.write("    ")
                    f.write(f"{owner}{comma}")
                    if i % 16 == 15 or i == max_province_id:
                        f.write("\n")
                    else:
                        f.write(" ")

                f.write("};\n")

            # ---- province_cores ----
            core_pairs = []
            for province_id, cores in sorted(valid_cores.items()):
                for country_id in sorted(cores):
                    core_pairs.append((province_id, country_id_remap.get(country_id, country_id)))

            with open(f"{output_dir}/province_cores.h", 'w') as f:
                f.write("#ifndef PROVINCE_CORES_H\n")
                f.write("#define PROVINCE_CORES_H\n\n")
                f.write("typedef struct {\n")
                f.write("    unsigned short province_id;\n")
                f.write("    unsigned char  country_id;\n")
                f.write("} ProvinceCore;\n\n")
                f.write(f"#define PROVINCE_CORE_COUNT {len(core_pairs)}\n\n")
                f.write("extern ProvinceCore province_cores[PROVINCE_CORE_COUNT];\n\n")
                f.write("#endif\n")

            with open(f"{output_dir}/province_cores.c", 'w') as f:
                f.write("#include \"province_cores.h\"\n\n")
                f.write("ProvinceCore province_cores[PROVINCE_CORE_COUNT] = {\n")
                for i, (province_id, country_id) in enumerate(core_pairs):
                    comma = ',' if i < len(core_pairs) - 1 else ''
                    f.write(f"    {{{province_id}, {country_id}}}{comma}\n")
                f.write("};\n")

            message = (
                f"Exported to {output_dir}\n\n"
                f"- countries.h/c ({len(self.countries)} countries)\n"
                f"- province_owners.h/c ({len(valid_owners)} provinces)\n"
                f"- province_cores.h/c ({len(core_pairs)} cores)"
            )
            if water_ownership_fixed > 0:
                message += f"\n\n\u26a0 Fixed {water_ownership_fixed} water provinces that had owners"
            skipped = len(self.province_owners) - len(valid_owners)
            if skipped > 0:
                message += f"\n\u26a0 Skipped {skipped} provinces not in map"

            messagebox.showinfo("Export Complete", message)

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}\n\nCheck console for details")
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------
    # SAVE / LOAD
    # ------------------------------------------------------------------

    def save_project(self):
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return

        data = {
            'countries':       {str(k): v for k, v in self.countries.items()},
            'province_owners': {str(k): v for k, v in self.province_owners.items()},
            'province_cores':  {str(k): list(v) for k, v in self.province_cores.items()},
            'next_country_id': self.next_country_id,
        }

        for country in data['countries'].values():
            country['provinces'] = list(country['provinces'])
            if 'capital' not in country:
                country['capital'] = NO_CAP

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        messagebox.showinfo("Success", "Project saved")

    def load_project(self):
        from tkinter import filedialog

        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.countries       = {int(k): v for k, v in data['countries'].items()}
            self.next_country_id = data['next_country_id']

            for country in self.countries.values():
                country['provinces'] = set(country['provinces'])
                country['color']     = tuple(country['color'])
                # Backward compat: old saves without 'capital'
                if 'capital' not in country:
                    country['capital'] = NO_CAP

            # ---- Detect and remap 1-indexed saves ----
            remapped = False
            if self.countries and min(self.countries.keys()) == 1:
                old_ids = sorted(self.countries.keys())
                remap   = {old: old - 1 for old in old_ids}

                self.countries       = {remap[k]: v for k, v in self.countries.items()}
                self.next_country_id = max(self.countries.keys()) + 1

                # Old format: 0 = unowned; remap non-zero owner ids
                raw_owners = {}
                for k, v in data['province_owners'].items():
                    raw_owners[int(k)] = UNOWNED if v == 0 else remap.get(v, UNOWNED)

                raw_cores = {int(k): {remap.get(cid, cid) for cid in v}
                             for k, v in data.get('province_cores', {}).items()}

                remapped = True
            else:
                # Current format — but upgrade old 0-sentinel to UNOWNED just in case
                raw_owners = {}
                for k, v in data['province_owners'].items():
                    raw_owners[int(k)] = UNOWNED if v == 0 else v

                raw_cores = {int(k): set(v)
                             for k, v in data.get('province_cores', {}).items()}

            # ---- Filter to currently loaded map (if any) ----
            valid_ids = set(self.province_id_to_color.keys())

            if valid_ids:
                self.province_owners = {pid: o  for pid, o  in raw_owners.items() if pid in valid_ids}
                self.province_cores  = {pid: cs for pid, cs in raw_cores.items()  if pid in valid_ids}
                skipped  = len(raw_owners) - len(self.province_owners)
                skip_msg = f"\n({skipped} provinces skipped \u2014 not in current map)" if skipped else ""
            else:
                self.province_owners = raw_owners
                self.province_cores  = raw_cores
                skip_msg = ""

            self.refresh_country_list()
            self.update_display()

            remap_msg = "\n(1-indexed save detected \u2014 remapped to 0-indexed)" if remapped else ""
            messagebox.showinfo("Success", f"Project loaded{skip_msg}{remap_msg}")

        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x800")
    app = ProvinceMapEditor(root)
    root.mainloop()