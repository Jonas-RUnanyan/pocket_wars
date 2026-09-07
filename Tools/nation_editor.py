"""
Nation Editor — merged author tool for Pocket Wars
(replaces country_filler.py + political_editor.py — those are now retired)

One Country record now holds BOTH identity (name/color/capital/borders/cores)
AND politics (ideology support/ruling ideology/stability/leader roster)
together, exported from one shared country list — the old two-tool split
made it possible for political_data.h to silently go stale relative to
countries.c whenever a country was added/removed in one tool but not
re-exported in the other. That class of bug is now structurally impossible.

FORMABLE NATIONS:
A country flagged "formable" starts dormant (not existing, not playable,
not part of the turn rotation) and has NO authored politics — it inherits
stability/support/leaders from whoever forms it at runtime (see FORM_NATION
in decisions.cpp). Its "Edit Politics" button is disabled accordingly.

POTENTIAL CORES vs REAL CORES:
Regular "Core States" mode writes to province_cores.c — always active,
checked by is_core() unconditionally. A NEW "Potential Cores" mode (only
usable on formable countries) writes to a SEPARATE formable_cores.c —
inert data that only becomes real cores at the moment that nation is
actually formed (decisions.cpp applies them automatically inside the
FORM_NATION effect). Doesn't make sense for Austria-Hungary to core all of
central Europe before it exists.

DYNAMIC IDEOLOGY NAMES:
Each country can have up to 4 optional display-name overrides, one per
ruling ideology (e.g. "Kingdom of Italy" under Autocracy vs "Italian
Republic" under Democracy). Blank = falls back to the base name. Lives on
the Country record itself (identity), not on CountryPolitics — a country's
name-under-ideology-X doesn't change just because ITS stability changed.

PORTRAITS: dropped per instruction — no portraits_manifest.csv anymore.
portrait_id stays on Leader purely as SET_LEADER's stable lookup key, not
as an art-pipeline artifact.
"""

import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
import json
import re

UNOWNED = 0xFF
NO_CAP = 0xFFFF

IDEOLOGIES = ["Fascism", "Democracy", "Communism", "Autocracy"]
IDEOLOGY_COUNT = len(IDEOLOGIES)

DEFAULT_SUPPORT   = [25, 25, 25, 25]
DEFAULT_STABILITY = 50
DEFAULT_RULING    = 3

LEADER_NONE = 0xFF
MAX_LEADERS = 255


def escape_c_string(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


class NationEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Nation Editor")

        # Map/province state
        self.province_map_img = None
        self.province_colors = {}
        self.province_id_to_color = {}
        self.province_names = {}
        self.province_is_water = {}

        # Unified country records: identity + politics together
        self.countries = {}          # country_id -> dict, see default_country()
        self.next_country_id = 0

        self.province_owners = {}
        self.province_cores = {}        # real, always-active cores: pid -> set(country_id)
        self.potential_cores = {}       # formable-only cores: pid -> set(country_id)

        self.leaders = {}               # global roster: leader_id -> {name,country_id,ideology}
        self.next_leader_id = 0

        self.active_country_id = None
        self.display_img = None
        self.photo = None

        self.mode = tk.StringVar(value='ownership')

        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        self.politics_win = None
        self.politics_cid = None
        self.leader_listboxes = []
        self.leader_list_ids = [[] for _ in range(IDEOLOGY_COUNT)]

        self.setup_gui()

    def default_country(self, name, color):
        return {
            'name': name, 'color': color, 'capital': NO_CAP,
            'is_formable': False, 'ideology_names': [None] * IDEOLOGY_COUNT,
            'support': list(DEFAULT_SUPPORT), 'ruling': DEFAULT_RULING, 'stability': DEFAULT_STABILITY,
            'current_leader': [None] * IDEOLOGY_COUNT,
        }

    # ------------------------------------------------------------------
    # PROVINCE DATA PARSER (unchanged from country_filler.py)
    # ------------------------------------------------------------------

    def parse_province_data_c(self, filepath):
        provinces = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'Province\s+provinces\[.*?\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
        if not match:
            raise ValueError("Could not find provinces array in province_data.c")
        pattern = r'\{\s*"([^"]+)"\s*,\s*0x([0-9A-Fa-f]+)\s*,\s*\d+\s*,\s*(\d+)(?:,\s*\d+)*\s*\}'
        matches = re.findall(pattern, match.group(1))
        province_id = 0
        for name, color_hex, is_water in matches:
            rgb24_int = int(color_hex, 16)
            rgb24 = ((rgb24_int >> 16) & 0xFF, (rgb24_int >> 8) & 0xFF, rgb24_int & 0xFF)
            provinces[province_id] = {'name': name, 'color': rgb24, 'is_water': int(is_water)}
            province_id += 1
        return provinces

    # ------------------------------------------------------------------
    # GUI SETUP
    # ------------------------------------------------------------------

    def setup_gui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.Frame(main_frame, width=260)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)

        ttk.Label(left_panel, text="Countries", font=('Arial', 12, 'bold')).pack(pady=5)

        mode_frame = ttk.LabelFrame(left_panel, text="Mode", padding=5)
        mode_frame.pack(fill=tk.X, pady=5)
        ttk.Radiobutton(mode_frame, text="Ownership",  variable=self.mode, value='ownership',
                        command=self.on_mode_change).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Core States", variable=self.mode, value='cores',
                        command=self.on_mode_change).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Capital",     variable=self.mode, value='capital',
                        command=self.on_mode_change).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Potential Cores (formable only)", variable=self.mode,
                        value='potential_cores', command=self.on_mode_change).pack(anchor=tk.W)

        self.country_listbox = tk.Listbox(left_panel, height=14)
        self.country_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.country_listbox.bind('<<ListboxSelect>>', self.on_country_select)

        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Add Country",    command=self.add_country).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Edit Country",   command=self.edit_country).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Delete Country", command=self.delete_country).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Edit Politics...", command=self.open_politics_editor).pack(fill=tk.X, pady=2)

        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Button(left_panel, text="Load Map",     command=self.load_map).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Export to C",  command=self.export_to_c).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Save Project", command=self.save_project).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Load Project", command=self.load_project).pack(fill=tk.X, pady=2)
        ttk.Button(left_panel, text="Import Legacy Projects...", command=self.import_legacy_projects).pack(fill=tk.X, pady=2)

        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(left_panel, text="Zoom Controls", font=('Arial', 10, 'bold')).pack(pady=5)
        ttk.Button(left_panel, text="Reset View", command=self.reset_view).pack(fill=tk.X, pady=2)
        self.zoom_label = ttk.Label(left_panel, text="Zoom: 100%")
        self.zoom_label.pack(pady=2)

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

    def on_mode_change(self):
        self.update_display()
        if self.active_country_id is not None:
            country = self.countries[self.active_country_id]
            mode = self.mode.get()
            hint = {
                'ownership': "click to assign/unassign ownership",
                'cores':     "click to add/remove REAL cores",
                'capital':   "click an owned province to set as capital",
                'potential_cores': "click to add/remove POTENTIAL cores (formable only, real once formed)",
            }.get(mode, "")
            self.status_label.config(text=f"Active: {country['name']} — {hint}")

    # ------------------------------------------------------------------
    # MAP LOADING (unchanged from country_filler.py)
    # ------------------------------------------------------------------

    def load_map(self):
        province_data_file = filedialog.askopenfilename(title="Select province_data.c",
                                                          filetypes=[("C source files", "*.c"), ("All files", "*.*")])
        if not province_data_file:
            return
        map_file = filedialog.askopenfilename(title="Select Province Map",
                                               filetypes=[("Image files", "*.png *.bmp"), ("All files", "*.*")])
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

            self.province_colors = {}
            self.province_id_to_color = {}
            self.province_names = {}
            self.province_is_water = {}

            found, skipped = 0, 0
            for province_id, data in parsed_provinces.items():
                color = data['color']
                if color in colors_in_map:
                    self.province_colors[color] = province_id
                    self.province_id_to_color[province_id] = color
                    self.province_names[province_id] = data['name']
                    self.province_is_water[province_id] = data['is_water']
                    if province_id not in self.province_owners:
                        self.province_owners[province_id] = UNOWNED
                    if province_id not in self.province_cores:
                        self.province_cores[province_id] = set()
                    if province_id not in self.potential_cores:
                        self.potential_cores[province_id] = set()
                    found += 1
                else:
                    skipped += 1

            valid_ids = set(self.province_id_to_color.keys())
            for pid in [p for p in list(self.province_owners) if p not in valid_ids]:
                del self.province_owners[pid]
            for pid in [p for p in list(self.province_cores) if p not in valid_ids]:
                del self.province_cores[pid]
            for pid in [p for p in list(self.potential_cores) if p not in valid_ids]:
                del self.potential_cores[pid]

            self.reset_view()
            msg = f"Loaded {found} provinces from map"
            if skipped: msg += f" (skipped {skipped} not in map)"
            self.status_label.config(text=msg)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load map: {e}")

    # ------------------------------------------------------------------
    # VIEW (unchanged from country_filler.py)
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
        old_zoom = self.zoom_level
        self.zoom_level = max(0.1, min(10.0, self.zoom_level * zoom_factor))
        change = self.zoom_level / old_zoom
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
            self.pan_x += dx; self.pan_y += dy
            self.drag_start_x = event.x; self.drag_start_y = event.y
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

        pixels = self.province_map_img.load()
        color = pixels[x, y]
        province_id = self.province_colors.get(color)
        if province_id is None:
            return

        province_name = self.province_names.get(province_id, f"Province {province_id}")
        country = self.countries[self.active_country_id]
        country_name = country['name']
        is_water = self.province_is_water.get(province_id, 0)
        mode = self.mode.get()

        if mode == 'ownership':
            if country.get('is_formable'):
                self.status_label.config(text=f"{country_name} is a formable nation — it can't own provinces until formed")
                return
            if is_water:
                self.status_label.config(text=f"{province_name} is water — cannot assign ownership")
                return
            current_owner = self.province_owners.get(province_id, UNOWNED)
            if current_owner == self.active_country_id:
                self.province_owners[province_id] = UNOWNED
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

        elif mode == 'potential_cores':
            if not country.get('is_formable'):
                self.status_label.config(text=f"{country_name} is not formable — potential cores only apply to formable nations")
                return
            cores = self.potential_cores.get(province_id, set())
            if self.active_country_id in cores:
                cores.discard(self.active_country_id)
                self.status_label.config(text=f"Removed {province_name} as POTENTIAL core of {country_name}")
            else:
                cores.add(self.active_country_id)
                self.status_label.config(text=f"Added {province_name} as POTENTIAL core of {country_name} (real once formed)")
            self.potential_cores[province_id] = cores

        elif mode == 'capital':
            if country.get('is_formable'):
                self.status_label.config(text=f"{country_name} is a formable nation — no starting capital")
                return
            current_owner = self.province_owners.get(province_id, UNOWNED)
            if current_owner != self.active_country_id:
                self.status_label.config(text=f"{province_name} is not owned by {country_name} — cannot set as capital")
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

        display = Image.new('RGB', self.province_map_img.size)
        pixels = self.province_map_img.load()
        display_pixels = display.load()
        width, height = self.province_map_img.size
        mode = self.mode.get()

        capital_province = None
        if mode == 'capital' and self.active_country_id is not None:
            cap = self.countries[self.active_country_id].get('capital', NO_CAP)
            if cap != NO_CAP:
                capital_province = cap

        for y in range(height):
            for x in range(width):
                color = pixels[x, y]
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

                elif mode == 'potential_cores':
                    if self.active_country_id is not None:
                        cores = self.potential_cores.get(province_id, set())
                        if self.active_country_id in cores:
                            c = self.countries.get(self.active_country_id)
                            base = c['color'] if c else (100, 100, 100)
                            display_pixels[x, y] = tuple(v // 2 for v in base)
                        else:
                            display_pixels[x, y] = (100, 100, 100)
                    else:
                        display_pixels[x, y] = (100, 100, 100)

                elif mode == 'capital':
                    if self.active_country_id is not None:
                        owner_id = self.province_owners.get(province_id, UNOWNED)
                        if owner_id == self.active_country_id:
                            if province_id == capital_province:
                                display_pixels[x, y] = (255, 220, 0)
                            else:
                                c = self.countries.get(self.active_country_id)
                                display_pixels[x, y] = c['color'] if c else (100, 100, 100)
                        else:
                            display_pixels[x, y] = (60, 60, 60)
                    else:
                        display_pixels[x, y] = (100, 100, 100)

        zoomed_w = int(width * self.zoom_level)
        zoomed_h = int(height * self.zoom_level)
        zoomed = display.resize((zoomed_w, zoomed_h), Image.NEAREST)
        self.display_img = zoomed
        self.photo = ImageTk.PhotoImage(zoomed)
        self.canvas.delete("all")
        self.canvas.create_image(self.pan_x, self.pan_y, anchor=tk.NW, image=self.photo)

    # ------------------------------------------------------------------
    # COUNTRY CRUD
    # ------------------------------------------------------------------

    def add_country(self):
        dialog = CountryDialog(self.root)
        if dialog.result_data is None:
            return
        cid = self.next_country_id
        self.next_country_id += 1
        d = dialog.result_data
        c = self.default_country(d['name'], d['color'])
        c['is_formable'] = d['is_formable']
        c['ideology_names'] = d['ideology_names']
        self.countries[cid] = c
        self.refresh_country_list()
        self.status_label.config(text=f"Added country: {d['name']}")

    def edit_country(self):
        selection = self.country_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a country to edit")
            return
        cid = list(self.countries.keys())[selection[0]]
        country = self.countries[cid]

        dialog = CountryDialog(self.root, initial=country)
        if dialog.result_data is None:
            return
        d = dialog.result_data
        country['name'] = d['name']
        country['color'] = d['color']
        country['is_formable'] = d['is_formable']
        country['ideology_names'] = d['ideology_names']

        self.refresh_country_list()
        self.update_display()

    def delete_country(self):
        selection = self.country_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a country to delete")
            return
        cid = list(self.countries.keys())[selection[0]]
        country = self.countries[cid]

        if not messagebox.askyesno("Confirm Delete", f"Delete {country['name']}? Also deletes any leaders belonging to it."):
            return

        for pid, owner_id in list(self.province_owners.items()):
            if owner_id == cid:
                self.province_owners[pid] = UNOWNED
        for cores in self.province_cores.values():
            cores.discard(cid)
        for cores in self.potential_cores.values():
            cores.discard(cid)
        for lid in [lid for lid, l in self.leaders.items() if l['country_id'] == cid]:
            del self.leaders[lid]

        del self.countries[cid]
        self.refresh_country_list()
        self.update_display()

    def on_country_select(self, event):
        selection = self.country_listbox.curselection()
        if selection:
            self.active_country_id = list(self.countries.keys())[selection[0]]
            country = self.countries[self.active_country_id]
            mode = self.mode.get()
            hint = {
                'ownership': "click to assign/unassign ownership",
                'cores':     "click to add/remove REAL cores",
                'capital':   "click an owned province to set as capital",
                'potential_cores': "click to add/remove POTENTIAL cores (formable only, real once formed)",
            }.get(mode, "")
            self.status_label.config(text=f"Active: {country['name']} — {hint}")
            if mode in ('cores', 'capital', 'potential_cores'):
                self.update_display()

    def refresh_country_list(self):
        self.country_listbox.delete(0, tk.END)
        for cid, country in self.countries.items():
            province_count = sum(1 for o in self.province_owners.values() if o == cid)
            core_count = sum(1 for c in self.province_cores.values() if cid in c)
            cap = country.get('capital', NO_CAP)
            cap_str = ""
            if cap != NO_CAP:
                cap_name = self.province_names.get(cap, f"#{cap}")
                cap_str = f" \u2605{cap_name}"
            tag = " [FORMABLE]" if country.get('is_formable') else ""
            self.country_listbox.insert(tk.END, f"{country['name']} ({province_count}P / {core_count}C){cap_str}{tag}")

    # ------------------------------------------------------------------
    # POLITICS EDITOR (Toplevel — disabled for formable countries)
    # ------------------------------------------------------------------

    def open_politics_editor(self):
        selection = self.country_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a country first")
            return
        cid = list(self.countries.keys())[selection[0]]
        country = self.countries[cid]
        if country['is_formable']:
            messagebox.showinfo("Formable Nation",
                                 "Formable nations inherit politics from whoever forms them — nothing to edit here.")
            return

        self.politics_cid = cid
        win = tk.Toplevel(self.root)
        win.title(f"Politics — {country['name']}")
        win.geometry("620x720")
        self.politics_win = win

        canvas = tk.Canvas(win, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        stab_frame = ttk.LabelFrame(body, text="Stability (0-100)", padding=8)
        stab_frame.pack(fill=tk.X, pady=5, padx=8)
        self.stability_var = tk.IntVar(value=country['stability'])
        ttk.Scale(stab_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.stability_var,
                  command=lambda e: self.on_politics_field_change()).pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.stability_readout = ttk.Label(stab_frame, text=str(country['stability']), width=4)
        self.stability_readout.pack(side=tk.LEFT, padx=5)

        support_frame = ttk.LabelFrame(body, text="Ideology Support & Ruling Party", padding=8)
        support_frame.pack(fill=tk.X, pady=5, padx=8)

        self.support_vars = []
        self.ruling_var = tk.IntVar(value=country['ruling'])
        for i, ideo in enumerate(IDEOLOGIES):
            row = ttk.Frame(support_frame)
            row.pack(fill=tk.X, pady=3)
            ttk.Radiobutton(row, variable=self.ruling_var, value=i, width=6,
                            command=self.on_politics_field_change).pack(side=tk.LEFT)
            ttk.Label(row, text=ideo, width=11).pack(side=tk.LEFT, padx=(4, 8))
            sup_var = tk.IntVar(value=country['support'][i])
            self.support_vars.append(sup_var)
            spin = ttk.Spinbox(row, from_=0, to=100, width=5, textvariable=sup_var,
                                command=self.on_politics_field_change)
            spin.pack(side=tk.LEFT)
            spin.bind('<KeyRelease>', lambda e: self.on_politics_field_change())
            ttk.Label(row, text="%").pack(side=tk.LEFT, padx=(2, 0))

        self.sum_label = ttk.Label(support_frame, text="Total: 100%", font=('Arial', 10, 'bold'))
        self.sum_label.pack(anchor=tk.E, pady=(6, 0))
        ttk.Button(support_frame, text="Normalize to 100%", command=self.normalize_support).pack(anchor=tk.E, pady=4)

        roster_frame = ttk.LabelFrame(body, text="Leader Rosters (per ideology)", padding=8)
        roster_frame.pack(fill=tk.X, pady=5, padx=8)
        ttk.Label(roster_frame,
                  text="Double-click, or select + \u2605 Set Active, to change who's currently in charge.",
                  foreground="#555").pack(anchor=tk.W, pady=(0, 8))

        self.leader_listboxes = []
        for i, ideo in enumerate(IDEOLOGIES):
            sub = ttk.LabelFrame(roster_frame, text=ideo, padding=6)
            sub.pack(fill=tk.X, pady=4)
            lb = tk.Listbox(sub, height=4)
            lb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            lb.bind('<Double-Button-1>', lambda e, idx=i: self.set_active_leader(idx))
            self.leader_listboxes.append(lb)
            btns = ttk.Frame(sub)
            btns.pack(side=tk.LEFT, padx=(6, 0))
            ttk.Button(btns, text="Add", width=12, command=lambda idx=i: self.add_leader(idx)).pack(pady=1)
            ttk.Button(btns, text="Rename", width=12, command=lambda idx=i: self.rename_leader(idx)).pack(pady=1)
            ttk.Button(btns, text="\u2605 Set Active", width=12, command=lambda idx=i: self.set_active_leader(idx)).pack(pady=1)
            ttk.Button(btns, text="Delete", width=12, command=lambda idx=i: self.delete_leader(idx)).pack(pady=1)

        self.refresh_all_leader_lists()

        def on_close():
            self.commit_politics_to_active()
            self.politics_win = None
            self.politics_cid = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

    def on_politics_field_change(self):
        self.stability_readout.config(text=str(int(self.stability_var.get())))
        self.commit_politics_to_active()
        self.update_sum_label()
        self.refresh_country_list()

    def commit_politics_to_active(self):
        if self.politics_cid is None:
            return
        c = self.countries[self.politics_cid]
        c['stability'] = int(self.stability_var.get())
        c['ruling'] = int(self.ruling_var.get())
        for i in range(IDEOLOGY_COUNT):
            try:
                c['support'][i] = int(self.support_vars[i].get())
            except (ValueError, tk.TclError):
                c['support'][i] = 0

    def update_sum_label(self):
        try:
            total = sum(int(v.get()) for v in self.support_vars)
        except (ValueError, tk.TclError):
            total = -1
        ok = (total == 100)
        self.sum_label.config(text=f"Total: {total}%", foreground=("black" if ok else "red"))

    def normalize_support(self):
        try:
            raw = [max(0, int(v.get())) for v in self.support_vars]
        except (ValueError, tk.TclError):
            raw = list(DEFAULT_SUPPORT)
        total = sum(raw)
        if total == 0:
            raw, total = list(DEFAULT_SUPPORT), 100
        scaled = [round(v * 100 / total) for v in raw]
        diff = 100 - sum(scaled)
        scaled[scaled.index(max(scaled))] += diff
        for i, v in enumerate(scaled):
            self.support_vars[i].set(v)
        self.on_politics_field_change()

    # ------------------------------------------------------------------
    # LEADER ROSTER MANAGEMENT (adapted from political_editor.py)
    # ------------------------------------------------------------------

    def refresh_all_leader_lists(self):
        for i in range(IDEOLOGY_COUNT):
            self.refresh_leader_list(i)

    def refresh_leader_list(self, ideology_idx):
        lb = self.leader_listboxes[ideology_idx]
        lb.delete(0, tk.END)
        self.leader_list_ids[ideology_idx] = []
        if self.politics_cid is None:
            return
        c = self.countries[self.politics_cid]
        active_lid = c['current_leader'][ideology_idx]
        roster = [(lid, l) for lid, l in self.leaders.items()
                  if l['country_id'] == self.politics_cid and l['ideology'] == ideology_idx]
        roster.sort(key=lambda pair: pair[0])
        for lid, leader in roster:
            marker = "\u2605 " if lid == active_lid else "   "
            lb.insert(tk.END, f"{marker}{leader['name']}")
            self.leader_list_ids[ideology_idx].append(lid)

    def _selected_leader_id(self, ideology_idx):
        lb = self.leader_listboxes[ideology_idx]
        sel = lb.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a leader in this ideology's list first")
            return None
        return self.leader_list_ids[ideology_idx][sel[0]]

    def add_leader(self, ideology_idx):
        if self.politics_cid is None:
            return
        name = simpledialog.askstring("Add Leader", f"Name of new {IDEOLOGIES[ideology_idx]} leader:", parent=self.politics_win)
        if not name:
            return
        leader_id = self.next_leader_id
        self.next_leader_id += 1
        self.leaders[leader_id] = {'name': name, 'country_id': self.politics_cid, 'ideology': ideology_idx}
        c = self.countries[self.politics_cid]
        if c['current_leader'][ideology_idx] is None:
            c['current_leader'][ideology_idx] = leader_id
        self.refresh_leader_list(ideology_idx)
        self.refresh_country_list()

    def rename_leader(self, ideology_idx):
        leader_id = self._selected_leader_id(ideology_idx)
        if leader_id is None:
            return
        current = self.leaders[leader_id]['name']
        new_name = simpledialog.askstring("Rename Leader", "New name:", initialvalue=current, parent=self.politics_win)
        if new_name:
            self.leaders[leader_id]['name'] = new_name
            self.refresh_leader_list(ideology_idx)
            self.refresh_country_list()

    def set_active_leader(self, ideology_idx):
        leader_id = self._selected_leader_id(ideology_idx)
        if leader_id is None:
            return
        c = self.countries[self.politics_cid]
        c['current_leader'][ideology_idx] = leader_id
        self.refresh_leader_list(ideology_idx)
        self.refresh_country_list()

    def delete_leader(self, ideology_idx):
        leader_id = self._selected_leader_id(ideology_idx)
        if leader_id is None:
            return
        name = self.leaders[leader_id]['name']
        if not messagebox.askyesno("Confirm Delete", f"Delete leader '{name}'?", parent=self.politics_win):
            return
        c = self.countries[self.politics_cid]
        if c['current_leader'][ideology_idx] == leader_id:
            c['current_leader'][ideology_idx] = None
        del self.leaders[leader_id]
        self.refresh_leader_list(ideology_idx)
        self.refresh_country_list()

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def export_to_c(self):
        if self.politics_cid is not None:
            self.commit_politics_to_active()

        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return

        try:
            valid_province_ids = set(self.province_id_to_color.keys())

            valid_owners, water_fixed = {}, 0
            for pid, owner in self.province_owners.items():
                if pid in valid_province_ids:
                    is_water = self.province_is_water.get(pid, 0)
                    if is_water and owner != UNOWNED:
                        valid_owners[pid] = UNOWNED; water_fixed += 1
                    else:
                        valid_owners[pid] = owner

            valid_cores = {pid: cores for pid, cores in self.province_cores.items() if pid in valid_province_ids}
            valid_potential = {pid: cores for pid, cores in self.potential_cores.items() if pid in valid_province_ids}

            sorted_ids = sorted(self.countries.keys())
            remap = {old: new for new, old in enumerate(sorted_ids)}
            country_count = len(sorted_ids)

            bad_leaders = [l for l in self.leaders.values() if self.countries.get(l['country_id'], {}).get('is_formable')]
            if bad_leaders:
                if not messagebox.askyesno("Leaders on formable countries",
                                            f"{len(bad_leaders)} leader(s) belong to formable countries (shouldn't happen via the UI). "
                                            f"Export anyway? They'll be exported but never used."):
                    return

            # ---- countries.h ----
            with open(f"{output_dir}/countries.h", 'w', encoding='utf-8') as f:
                f.write("#ifndef COUNTRIES_H\n#define COUNTRIES_H\n\n")
                f.write("// ideology_names index order must match Ideology enum in political_data.h\n")
                f.write("// (Fascism=0, Democracy=1, Communism=2, Autocracy=3)\n")
                f.write("typedef struct {\n")
                f.write("    const char*    name;\n")
                f.write("    const char*    ideology_names[4]; // per-ruling-ideology override, NULL = use base name\n")
                f.write("    unsigned short color;\n")
                f.write("    unsigned short capital;\n")
                f.write("    unsigned char  is_formable; // 1 = dormant at start, no authored politics, inherits on formation\n")
                f.write("} Country;\n\n")
                f.write(f"#define COUNTRY_COUNT {country_count}\n")
                f.write("#define NO_CAPITAL    0xFFFF\n\n")
                f.write("extern const Country countries[COUNTRY_COUNT];\n\n")
                f.write("#endif\n")

            # ---- countries.c ----
            with open(f"{output_dir}/countries.c", 'w', encoding='utf-8') as f:
                f.write('#include "countries.h"\n\n')
                f.write("const Country countries[COUNTRY_COUNT] = {\n")
                for i, old_id in enumerate(sorted_ids):
                    c = self.countries[old_id]
                    r, g, b = c['color']
                    bgr15 = 0x8000 | ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)
                    cap = c.get('capital', NO_CAP)
                    if cap != NO_CAP and valid_owners.get(cap, UNOWNED) != old_id:
                        cap = NO_CAP
                    names_str = ", ".join(
                        f'"{escape_c_string(n)}"' if n else "NULL" for n in c.get('ideology_names', [None]*4))
                    formable = 1 if c.get('is_formable') else 0
                    comma = ',' if i < country_count - 1 else ''
                    f.write(f'    {{"{escape_c_string(c["name"])}", {{{names_str}}}, '
                            f'0x{bgr15:04X}, 0x{cap:04X}, {formable}}}{comma}\n')
                f.write("};\n")

            # ---- province_owners.h/.c ----
            max_pid = max(valid_province_ids) if valid_province_ids else 0
            with open(f"{output_dir}/province_owners.h", 'w') as f:
                f.write("#ifndef PROVINCE_OWNERS_H\n#define PROVINCE_OWNERS_H\n\n")
                f.write(f"#define PROVINCE_OWNER_COUNT {max_pid + 1}\n")
                f.write("#define PROVINCE_UNOWNED      0xFF\n\n")
                f.write("extern unsigned char province_owners[PROVINCE_OWNER_COUNT];\n\n#endif\n")
            with open(f"{output_dir}/province_owners.c", 'w') as f:
                f.write('#include "province_owners.h"\n\n')
                f.write("unsigned char province_owners[PROVINCE_OWNER_COUNT] = {\n")
                for i in range(max_pid + 1):
                    raw = valid_owners.get(i, UNOWNED)
                    owner = 0xFF if raw == UNOWNED else remap.get(raw, 0xFF)
                    comma = ',' if i < max_pid else ''
                    if i % 16 == 0: f.write("    ")
                    f.write(f"{owner}{comma}")
                    f.write("\n" if (i % 16 == 15 or i == max_pid) else " ")
                f.write("};\n")

            # ---- province_cores.h/.c (REAL cores, unchanged format) ----
            core_pairs = [(pid, remap.get(cid, cid)) for pid, cores in sorted(valid_cores.items()) for cid in sorted(cores)]
            with open(f"{output_dir}/province_cores.h", 'w') as f:
                f.write("#ifndef PROVINCE_CORES_H\n#define PROVINCE_CORES_H\n\n")
                f.write("typedef struct {\n    unsigned short province_id;\n    unsigned char  country_id;\n} ProvinceCore;\n\n")
                f.write(f"#define PROVINCE_CORE_COUNT {len(core_pairs)}\n\n")
                f.write("extern ProvinceCore province_cores[PROVINCE_CORE_COUNT];\n\n#endif\n")
            with open(f"{output_dir}/province_cores.c", 'w') as f:
                f.write('#include "province_cores.h"\n\n')
                f.write("ProvinceCore province_cores[PROVINCE_CORE_COUNT] = {\n")
                for i, (pid, cid) in enumerate(core_pairs):
                    comma = ',' if i < len(core_pairs) - 1 else ''
                    f.write(f"    {{{pid}, {cid}}}{comma}\n")
                f.write("};\n")

            # ---- formable_cores.h/.c (NEW — potential cores, only real once formed) ----
            formable_pairs = [(pid, remap.get(cid, cid)) for pid, cores in sorted(valid_potential.items()) for cid in sorted(cores)]
            with open(f"{output_dir}/formable_cores.h", 'w') as f:
                f.write("#ifndef FORMABLE_CORES_H\n#define FORMABLE_CORES_H\n\n")
                f.write('#include "province_cores.h" // reuses ProvinceCore\n\n')
                f.write(f"#define FORMABLE_CORE_COUNT {len(formable_pairs)}\n\n")
                f.write("// Inert until the referenced country is actually formed (decisions.cpp applies\n")
                f.write("// these automatically inside the FORM_NATION effect) — NOT checked by is_core().\n")
                f.write("extern const ProvinceCore formable_cores[FORMABLE_CORE_COUNT];\n\n#endif\n")
            with open(f"{output_dir}/formable_cores.c", 'w') as f:
                f.write('#include "formable_cores.h"\n\n')
                f.write("const ProvinceCore formable_cores[FORMABLE_CORE_COUNT] = {\n")
                for i, (pid, cid) in enumerate(formable_pairs):
                    comma = ',' if i < len(formable_pairs) - 1 else ''
                    f.write(f"    {{{pid}, {cid}}}{comma}\n")
                f.write("};\n")

            # ---- political_data.h/.c ----
            sorted_leader_ids = sorted(self.leaders.keys())
            leader_array_index = {lid: idx for idx, lid in enumerate(sorted_leader_ids)}
            leader_count = len(sorted_leader_ids)

            with open(f"{output_dir}/political_data.h", 'w', encoding='utf-8') as f:
                f.write("#ifndef POLITICAL_DATA_H\n#define POLITICAL_DATA_H\n\n")
                f.write("typedef enum {\n")
                for i, ideo in enumerate(IDEOLOGIES):
                    comma = ',' if i < IDEOLOGY_COUNT - 1 else ''
                    f.write(f"    IDEOLOGY_{ideo.upper()} = {i}{comma}\n")
                f.write("} Ideology;\n\n")
                f.write(f"#define IDEOLOGY_COUNT {IDEOLOGY_COUNT}\n\n")
                f.write("#define LEADER_NONE 0xFF\n\n")
                f.write("typedef struct {\n    const char*   name;\n    unsigned char country_id;\n")
                f.write("    unsigned char ideology;\n    unsigned char portrait_id; // stable leader reference key\n} Leader;\n\n")
                f.write(f"#define LEADER_COUNT {leader_count}\n\n")
                f.write("extern const Leader leaders[LEADER_COUNT];\n\n")
                f.write("typedef struct {\n")
                f.write("    unsigned char ideology_support[IDEOLOGY_COUNT];\n")
                f.write("    unsigned char ruling_ideology;\n")
                f.write("    unsigned char stability;\n")
                f.write("    unsigned char current_leader[IDEOLOGY_COUNT];\n")
                f.write("} CountryPolitics;\n\n")
                f.write(f"#define COUNTRY_POLITICS_COUNT {country_count}\n\n")
                f.write("extern const CountryPolitics country_politics[COUNTRY_POLITICS_COUNT];\n\n#endif\n")

            with open(f"{output_dir}/political_data.c", 'w', encoding='utf-8') as f:
                f.write('#include "political_data.h"\n\n')
                f.write("const Leader leaders[LEADER_COUNT] = {\n")
                for idx, lid in enumerate(sorted_leader_ids):
                    l = self.leaders[lid]
                    old_cid = l['country_id']
                    new_cid = remap.get(old_cid, old_cid)
                    cname = self.countries.get(old_cid, {}).get('name', '?')
                    comma = ',' if idx < leader_count - 1 else ''
                    f.write(f'    {{"{escape_c_string(l["name"])}", {new_cid}, {l["ideology"]}, {lid}}}{comma}'
                            f'  // {cname} - {IDEOLOGIES[l["ideology"]]}\n')
                f.write("};\n\n")

                f.write("const CountryPolitics country_politics[COUNTRY_POLITICS_COUNT] = {\n")
                for i, old_id in enumerate(sorted_ids):
                    c = self.countries[old_id]
                    support_braces = "{" + ", ".join(str(v) for v in c['support']) + "}"
                    cur_vals = []
                    for lid in c['current_leader']:
                        cur_vals.append(str(leader_array_index[lid]) if lid in leader_array_index else "LEADER_NONE")
                    cur_braces = "{" + ", ".join(cur_vals) + "}"
                    comma = ',' if i < country_count - 1 else ''
                    f.write(f'    // {c["name"]}\n')
                    f.write(f'    {{{support_braces}, {c["ruling"]}, {c["stability"]}, {cur_braces}}}{comma}\n')
                f.write("};\n")

            message = (
                f"Exported to {output_dir}\n\n"
                f"- countries.h/c ({country_count} countries)\n"
                f"- province_owners.h/c ({len(valid_owners)} provinces)\n"
                f"- province_cores.h/c ({len(core_pairs)} real cores)\n"
                f"- formable_cores.h/c ({len(formable_pairs)} potential cores)\n"
                f"- political_data.h/c ({country_count} countries, {leader_count} leaders)"
            )
            if water_fixed:
                message += f"\n\u26a0 Fixed {water_fixed} water provinces that had owners"
            messagebox.showinfo("Export Complete", message)

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------
    # SAVE / LOAD (new unified project format)
    # ------------------------------------------------------------------

    def save_project(self):
        if self.politics_cid is not None:
            self.commit_politics_to_active()
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not filename:
            return
        data = {
            'countries': {str(k): {**v, 'color': list(v['color'])} for k, v in self.countries.items()},
            'next_country_id': self.next_country_id,
            'province_owners': self.province_owners,
            'province_cores': {str(k): list(v) for k, v in self.province_cores.items()},
            'potential_cores': {str(k): list(v) for k, v in self.potential_cores.items()},
            'leaders': self.leaders,
            'next_leader_id': self.next_leader_id,
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        messagebox.showinfo("Success", "Project saved")

    def load_project(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not filename:
            return
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.countries = {int(k): v for k, v in data['countries'].items()}
            for c in self.countries.values():
                c['color'] = tuple(c['color'])
            self.next_country_id = data['next_country_id']
            self.province_owners = {int(k): v for k, v in data['province_owners'].items()}
            self.province_cores = {int(k): set(v) for k, v in data.get('province_cores', {}).items()}
            self.potential_cores = {int(k): set(v) for k, v in data.get('potential_cores', {}).items()}
            self.leaders = {int(k): v for k, v in data.get('leaders', {}).items()}
            self.next_leader_id = data.get('next_leader_id', 0)
            self.refresh_country_list()
            self.update_display()
            messagebox.showinfo("Success", "Project loaded")
        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")

    # ------------------------------------------------------------------
    # MIGRATION FROM THE OLD TWO SEPARATE TOOLS
    # ------------------------------------------------------------------

    def import_legacy_projects(self):
        cf_path = filedialog.askopenfilename(title="Select OLD country_filler.py project JSON")
        if not cf_path:
            return
        with open(cf_path, 'r', encoding='utf-8') as f:
            cf_data = json.load(f)

        pe_path = filedialog.askopenfilename(title="Select OLD political_editor.py project JSON (Cancel to skip)")
        pe_data = None
        if pe_path:
            with open(pe_path, 'r', encoding='utf-8') as f:
                pe_data = json.load(f)

        try:
            raw_countries = {int(k): v for k, v in cf_data['countries'].items()}
            self.next_country_id = cf_data['next_country_id']

            self.countries = {}
            for cid, oc in raw_countries.items():
                c = self.default_country(oc['name'], tuple(oc['color']))
                c['capital'] = oc.get('capital', NO_CAP)
                self.countries[cid] = c

            self.province_owners = {int(k): v for k, v in cf_data['province_owners'].items()}
            self.province_cores = {int(k): set(v) for k, v in cf_data.get('province_cores', {}).items()}
            self.potential_cores = {pid: set() for pid in self.province_cores}

            if pe_data:
                politics = {int(k): v for k, v in pe_data['politics'].items()}
                for cid, pol in politics.items():
                    if cid in self.countries:
                        self.countries[cid]['support'] = pol['support']
                        self.countries[cid]['ruling'] = pol['ruling']
                        self.countries[cid]['stability'] = pol['stability']
                        self.countries[cid]['current_leader'] = pol['current_leader']
                self.leaders = {int(k): v for k, v in pe_data.get('leaders', {}).items()}
                self.next_leader_id = pe_data.get('next_leader_id', 0)

            self.refresh_country_list()
            self.update_display()
            messagebox.showinfo("Imported",
                                 "Legacy projects merged into the new unified format.\n\n"
                                 "Load your map (Load Map) to see provinces on the canvas, then Save Project "
                                 "to keep this as a proper unified project going forward.")
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")
            import traceback
            traceback.print_exc()


class CountryDialog(simpledialog.Dialog):
    def __init__(self, parent, initial=None):
        self.initial = initial or {}
        self.result_data = None
        self.color_val = self.initial.get('color', (128, 128, 128))
        super().__init__(parent, title="Country")

    def _hex(self, rgb):
        return '#%02x%02x%02x' % rgb

    def body(self, master):
        ttk.Label(master, text="Name:").grid(row=0, column=0, sticky='w', pady=2)
        self.name_var = tk.StringVar(value=self.initial.get('name', ''))
        entry = ttk.Entry(master, textvariable=self.name_var, width=30)
        entry.grid(row=0, column=1, columnspan=2, sticky='we', pady=2)

        ttk.Label(master, text="Color:").grid(row=1, column=0, sticky='w', pady=2)
        self.color_swatch = tk.Label(master, bg=self._hex(self.color_val), width=6, relief='sunken')
        self.color_swatch.grid(row=1, column=1, sticky='w')
        ttk.Button(master, text="Choose...", command=self.pick_color).grid(row=1, column=2, sticky='w')

        self.formable_var = tk.BooleanVar(value=self.initial.get('is_formable', False))
        ttk.Checkbutton(master, variable=self.formable_var,
                         text="Formable nation (dormant at start, not playable,\ninherits politics from whoever forms it)"
                         ).grid(row=2, column=0, columnspan=3, sticky='w', pady=(10, 4))

        ttk.Label(master, text="Ideology display-name overrides (blank = use name above):",
                  foreground="#555").grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 2))
        self.ideology_name_vars = []
        existing = self.initial.get('ideology_names', [None] * IDEOLOGY_COUNT)
        for i, ideo in enumerate(IDEOLOGIES):
            ttk.Label(master, text=f"  {ideo}:").grid(row=4 + i, column=0, sticky='w')
            var = tk.StringVar(value=existing[i] or '')
            ttk.Entry(master, textvariable=var, width=30).grid(row=4 + i, column=1, columnspan=2, sticky='we')
            self.ideology_name_vars.append(var)

        return entry

    def pick_color(self):
        c = colorchooser.askcolor(title="Choose country color", initialcolor=self.color_val)
        if c[0]:
            self.color_val = tuple(int(v) for v in c[0])
            self.color_swatch.config(bg=self._hex(self.color_val))

    def apply(self):
        name = self.name_var.get().strip() or "Unnamed"
        ideology_names = [v.get().strip() or None for v in self.ideology_name_vars]
        self.result_data = {
            'name': name,
            'color': self.color_val,
            'is_formable': bool(self.formable_var.get()),
            'ideology_names': ideology_names,
        }


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1300x820")
    app = NationEditor(root)
    root.mainloop()