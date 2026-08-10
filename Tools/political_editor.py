"""
Political Data Editor — author tool for Pocket Wars

Loads the existing countries.c (the source of truth for country IDs — this
tool does NOT add/remove/reorder countries, that's country_filler.py's job)
and lets you author, per country:

  - Ideology popularity (Fascism / Democracy / Communism / Autocracy), 0-100
    each, should sum to 100
  - Which ideology is actually RULING the country (not necessarily the most
    popular one)
  - Stability, 0-100
  - A LEADER ROSTER per ideology — not one fixed leader. Each ideology slot
    can hold any number of leaders over the country's history (e.g. Stalin,
    then Trotsky, both under Communism), and exactly one of them is marked
    "currently active" at a time. Overthrows/successions/resignations are
    just re-pointing which roster entry is active — no restructuring.

Exports political_data.h/political_data.c using the exact same
COUNTRY_POLITICS_COUNT and array order as countries.c, so country_id from
the rest of the game maps straight across — no remapping, no risk of
desyncing from province_owners.c/province_cores.c.

Also writes portraits_manifest.csv — one row per leader ever created — so
portrait art can be commissioned/painted against a known checklist, the
same way states_colors.csv drove the flag painting.

------------------------------------------------------------------------
PORTRAIT SYSTEM NOTE (not built yet, this is just planning ahead):
Each leader gets a stable portrait_id, assigned once at creation and never
reused or renumbered — deliberately DECOUPLED from the leader's position in
the exported leaders[] C array, since that array's order/length changes
every time you add, delete, or re-export leaders. portrait_id is what a
future portrait sheet/grit pipeline would key off of; it survives roster
edits, array-index shuffling never invalidates painted art.
------------------------------------------------------------------------
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import re
import csv

IDEOLOGIES = ["Fascism", "Democracy", "Communism", "Autocracy"]
IDEOLOGY_COUNT = len(IDEOLOGIES)

DEFAULT_SUPPORT   = [25, 25, 25, 25]
DEFAULT_STABILITY = 50
DEFAULT_RULING    = 3  # Autocracy — arbitrary but reasonable default for an unedited country

LEADER_NONE = 0xFF  # sentinel: no leader currently active for this ideology slot
MAX_LEADERS = 255    # LEADER_NONE reserves 0xFF, so array indices must stay 0-254


class PoliticalEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Political Data Editor")

        self.countries = []   # [{'id': int, 'name': str}, ...] — order = countries.c order, read-only here
        self.politics  = {}   # country_id -> political data dict
        self.leaders   = {}   # leader_id (stable, never reused) -> {'name','country_id','ideology'}
        self.next_leader_id = 0

        self.active_id      = None
        self._loading_form   = False  # guard against feedback loops while populating widgets

        # Parallel to each ideology's listbox: which leader_id each visible row corresponds to
        self.leader_list_ids = [[] for _ in range(IDEOLOGY_COUNT)]

        self.setup_gui()

    # ------------------------------------------------------------------
    # countries.c PARSER — same regex approach as country_filler.py.
    # Read-only: this tool trusts countries.c as ground truth and never
    # writes back to it, and never changes country order or count.
    # ------------------------------------------------------------------

    def parse_countries_c(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        match = re.search(r'Country\s+countries\[.*?\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
        if not match:
            raise ValueError("Could not find countries array in countries.c")

        pattern = r'\{\s*"([^"]+)"\s*,\s*0x[0-9A-Fa-f]+\s*,\s*0x[0-9A-Fa-f]+\s*\}'
        names = re.findall(pattern, match.group(1))

        if not names:
            raise ValueError("Found the countries array but couldn't parse any entries — "
                              "check the file matches the expected {\"Name\", 0xColor, 0xCapital} format")

        return [{'id': i, 'name': name} for i, name in enumerate(names)]

    def default_politics(self):
        return {
            'support':        list(DEFAULT_SUPPORT),
            'ruling':          DEFAULT_RULING,
            'stability':       DEFAULT_STABILITY,
            'current_leader': [None] * IDEOLOGY_COUNT,   # None = no active leader for that slot yet
        }

    # ------------------------------------------------------------------
    # GUI SETUP
    # ------------------------------------------------------------------

    def setup_gui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        # ---- Left: country list ----
        left = ttk.Frame(main, width=300)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)

        ttk.Label(left, text="Countries", font=('Arial', 12, 'bold')).pack(pady=5)

        self.country_listbox = tk.Listbox(left, height=32)
        self.country_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.country_listbox.bind('<<ListboxSelect>>', self.on_country_select)

        ttk.Separator(left, orient='horizontal').pack(fill=tk.X, pady=8)

        ttk.Button(left, text="Load countries.c", command=self.load_countries).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Save Project",     command=self.save_project).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Load Project",     command=self.load_project).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Export to C",      command=self.export_to_c).pack(fill=tk.X, pady=2)

        self.status_label = ttk.Label(self.root, text="Load countries.c to begin.", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # ---- Right: edit form (scrollable — leader rosters take real space) ----
        right_container = ttk.Frame(main)
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        canvas = tk.Canvas(right_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_container, orient=tk.VERTICAL, command=canvas.yview)
        right = ttk.Frame(canvas)

        right.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=right, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.form_title = ttk.Label(right, text="No country selected", font=('Arial', 13, 'bold'))
        self.form_title.pack(anchor=tk.W, pady=(0, 10))

        # Stability
        stab_frame = ttk.LabelFrame(right, text="Stability (0-100)", padding=8)
        stab_frame.pack(fill=tk.X, pady=5)
        self.stability_var = tk.IntVar(value=DEFAULT_STABILITY)
        stab_scale = ttk.Scale(stab_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                variable=self.stability_var, command=lambda e: self.on_field_change())
        stab_scale.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.stability_readout = ttk.Label(stab_frame, text=str(DEFAULT_STABILITY), width=4)
        self.stability_readout.pack(side=tk.LEFT, padx=5)

        # Ideology support + ruling
        support_frame = ttk.LabelFrame(right, text="Ideology Support & Ruling Party", padding=8)
        support_frame.pack(fill=tk.X, pady=5)

        header = ttk.Frame(support_frame)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Ruling", width=8).pack(side=tk.LEFT)
        ttk.Label(header, text="Ideology", width=11).pack(side=tk.LEFT, padx=(4, 8))
        ttk.Label(header, text="Support").pack(side=tk.LEFT)

        self.support_vars = []
        self.ruling_var    = tk.IntVar(value=DEFAULT_RULING)

        for i, ideo in enumerate(IDEOLOGIES):
            row = ttk.Frame(support_frame)
            row.pack(fill=tk.X, pady=3)

            ttk.Radiobutton(row, variable=self.ruling_var, value=i, width=6,
                            command=self.on_field_change).pack(side=tk.LEFT)
            ttk.Label(row, text=ideo, width=11).pack(side=tk.LEFT, padx=(4, 8))

            sup_var = tk.IntVar(value=DEFAULT_SUPPORT[i])
            self.support_vars.append(sup_var)
            sup_spin = ttk.Spinbox(row, from_=0, to=100, width=5, textvariable=sup_var,
                                    command=self.on_field_change)
            sup_spin.pack(side=tk.LEFT)
            sup_spin.bind('<KeyRelease>', lambda e: self.on_field_change())
            ttk.Label(row, text="%").pack(side=tk.LEFT, padx=(2, 0))

        self.sum_label = ttk.Label(support_frame, text="Total: 100%", font=('Arial', 10, 'bold'))
        self.sum_label.pack(anchor=tk.E, pady=(6, 0))
        ttk.Button(support_frame, text="Normalize to 100%", command=self.normalize_support).pack(anchor=tk.E, pady=4)

        # Leader rosters — one section per ideology
        roster_frame = ttk.LabelFrame(right, text="Leader Rosters (per ideology)", padding=8)
        roster_frame.pack(fill=tk.X, pady=5)

        ttk.Label(roster_frame,
                  text="Each ideology can hold any number of leaders over time. Double-click, or\n"
                       "select + \u2605 Set Active, to change who's currently in charge for that ideology.",
                  foreground="#555", justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 8))

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
            ttk.Button(btns, text="Add",        width=12, command=lambda idx=i: self.add_leader(idx)).pack(pady=1)
            ttk.Button(btns, text="Rename",     width=12, command=lambda idx=i: self.rename_leader(idx)).pack(pady=1)
            ttk.Button(btns, text="\u2605 Set Active", width=12, command=lambda idx=i: self.set_active_leader(idx)).pack(pady=1)
            ttk.Button(btns, text="Delete",     width=12, command=lambda idx=i: self.delete_leader(idx)).pack(pady=1)

        ttk.Label(right,
                  text=("Note: portrait IDs are auto-assigned when a leader is created and never change\n"
                        "afterward, even if the leader is later renamed or another leader is deleted. Portrait\n"
                        "art itself isn't wired into the game yet — see portraits_manifest.csv after exporting."),
                  foreground="#555", justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 10))

    # ------------------------------------------------------------------
    # LOAD countries.c
    # ------------------------------------------------------------------

    def load_countries(self):
        filepath = filedialog.askopenfilename(
            title="Select countries.c",
            filetypes=[("C source files", "*.c"), ("All files", "*.*")]
        )
        if not filepath:
            return

        try:
            self.countries = self.parse_countries_c(filepath)
            for c in self.countries:
                if c['id'] not in self.politics:
                    self.politics[c['id']] = self.default_politics()

            self.active_id = None
            self.form_title.config(text="No country selected")
            self.refresh_country_list()
            self.status_label.config(text=f"Loaded {len(self.countries)} countries")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load countries.c: {e}")

    def refresh_country_list(self):
        self.country_listbox.delete(0, tk.END)
        for c in self.countries:
            pol = self.politics.get(c['id'])
            tag = ""
            if pol:
                ruling_idx  = pol['ruling']
                ruling_name = IDEOLOGIES[ruling_idx][:3].upper()
                leader_id   = pol['current_leader'][ruling_idx]
                leader_name = self.leaders[leader_id]['name'] if leader_id in self.leaders else "no leader"
                sum_ok      = "" if sum(pol['support']) == 100 else " \u26a0"
                tag = f"  [{ruling_name} / {leader_name} / stab {pol['stability']}{sum_ok}]"
            self.country_listbox.insert(tk.END, f"{c['name']}{tag}")

    # ------------------------------------------------------------------
    # FORM <-> DATA
    # ------------------------------------------------------------------

    def on_country_select(self, event):
        selection = self.country_listbox.curselection()
        if not selection:
            return

        self.commit_form_to_active()
        self.active_id = self.countries[selection[0]]['id']
        self.load_form_from_active()

    def load_form_from_active(self):
        if self.active_id is None:
            return

        pol          = self.politics.setdefault(self.active_id, self.default_politics())
        country_name = next(c['name'] for c in self.countries if c['id'] == self.active_id)

        self._loading_form = True
        self.form_title.config(text=country_name)
        self.stability_var.set(pol['stability'])
        self.stability_readout.config(text=str(pol['stability']))
        self.ruling_var.set(pol['ruling'])
        for i in range(IDEOLOGY_COUNT):
            self.support_vars[i].set(pol['support'][i])
        self._loading_form = False

        self.update_sum_label()
        self.refresh_all_leader_lists()

    def commit_form_to_active(self):
        if self.active_id is None:
            return

        pol = self.politics.setdefault(self.active_id, self.default_politics())
        pol['stability'] = int(self.stability_var.get())
        pol['ruling']    = int(self.ruling_var.get())
        for i in range(IDEOLOGY_COUNT):
            try:
                pol['support'][i] = int(self.support_vars[i].get())
            except (ValueError, tk.TclError):
                pol['support'][i] = 0
        # current_leader[] is updated directly by add/rename/delete/set-active — nothing to commit here

    def on_field_change(self):
        if self._loading_form:
            return
        self.stability_readout.config(text=str(int(self.stability_var.get())))
        self.commit_form_to_active()
        self.update_sum_label()
        self.refresh_country_list()

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
        diff   = 100 - sum(scaled)          # rounding can land on 99/101 — dump remainder on the largest entry
        scaled[scaled.index(max(scaled))] += diff

        for i, v in enumerate(scaled):
            self.support_vars[i].set(v)

        self.on_field_change()

    # ------------------------------------------------------------------
    # LEADER ROSTER MANAGEMENT
    # ------------------------------------------------------------------

    def refresh_all_leader_lists(self):
        for i in range(IDEOLOGY_COUNT):
            self.refresh_leader_list(i)

    def refresh_leader_list(self, ideology_idx):
        lb = self.leader_listboxes[ideology_idx]
        lb.delete(0, tk.END)
        self.leader_list_ids[ideology_idx] = []

        if self.active_id is None:
            return

        pol         = self.politics.setdefault(self.active_id, self.default_politics())
        active_lid  = pol['current_leader'][ideology_idx]

        roster = [(lid, l) for lid, l in self.leaders.items()
                  if l['country_id'] == self.active_id and l['ideology'] == ideology_idx]
        roster.sort(key=lambda pair: pair[0])  # stable creation order

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
        if self.active_id is None:
            messagebox.showwarning("No Country Selected", "Select a country first")
            return

        name = simpledialog.askstring("Add Leader", f"Name of new {IDEOLOGIES[ideology_idx]} leader:")
        if not name:
            return

        leader_id = self.next_leader_id
        self.next_leader_id += 1
        self.leaders[leader_id] = {
            'name':       name,
            'country_id': self.active_id,
            'ideology':   ideology_idx,
        }

        pol = self.politics.setdefault(self.active_id, self.default_politics())
        if pol['current_leader'][ideology_idx] is None:
            pol['current_leader'][ideology_idx] = leader_id  # first leader for this slot — auto-activate

        self.refresh_leader_list(ideology_idx)
        self.refresh_country_list()

    def rename_leader(self, ideology_idx):
        leader_id = self._selected_leader_id(ideology_idx)
        if leader_id is None:
            return

        current = self.leaders[leader_id]['name']
        new_name = simpledialog.askstring("Rename Leader", "New name:", initialvalue=current)
        if new_name:
            self.leaders[leader_id]['name'] = new_name
            self.refresh_leader_list(ideology_idx)
            self.refresh_country_list()

    def set_active_leader(self, ideology_idx):
        leader_id = self._selected_leader_id(ideology_idx)
        if leader_id is None:
            return

        pol = self.politics.setdefault(self.active_id, self.default_politics())
        pol['current_leader'][ideology_idx] = leader_id
        self.refresh_leader_list(ideology_idx)
        self.refresh_country_list()

    def delete_leader(self, ideology_idx):
        leader_id = self._selected_leader_id(ideology_idx)
        if leader_id is None:
            return

        name = self.leaders[leader_id]['name']
        if not messagebox.askyesno("Confirm Delete", f"Delete leader '{name}'? This cannot be undone."):
            return

        pol = self.politics.setdefault(self.active_id, self.default_politics())
        if pol['current_leader'][ideology_idx] == leader_id:
            pol['current_leader'][ideology_idx] = None

        del self.leaders[leader_id]
        self.refresh_leader_list(ideology_idx)
        self.refresh_country_list()

    # ------------------------------------------------------------------
    # SAVE / LOAD PROJECT
    # ------------------------------------------------------------------

    def save_project(self):
        self.commit_form_to_active()

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return

        data = {
            'countries':      self.countries,
            'politics':       {str(k): v for k, v in self.politics.items()},
            'leaders':        {str(k): v for k, v in self.leaders.items()},
            'next_leader_id': self.next_leader_id,
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        messagebox.showinfo("Success", "Project saved")

    def load_project(self):
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.countries      = data['countries']
            self.politics       = {int(k): v for k, v in data['politics'].items()}
            self.leaders         = {int(k): v for k, v in data.get('leaders', {}).items()}
            self.next_leader_id = data.get('next_leader_id', 0)

            self.active_id = None
            self.form_title.config(text="No country selected")
            self.refresh_country_list()
            for i in range(IDEOLOGY_COUNT):
                self.leader_listboxes[i].delete(0, tk.END)
            messagebox.showinfo("Success", "Project loaded")
        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def export_to_c(self):
        self.commit_form_to_active()

        if not self.countries:
            messagebox.showwarning("Nothing to export", "Load countries.c first")
            return

        if len(self.leaders) > MAX_LEADERS:
            messagebox.showerror(
                "Too many leaders",
                f"{len(self.leaders)} leaders exist, but current_leader/portrait fields are unsigned char "
                f"with 0xFF reserved as LEADER_NONE — max {MAX_LEADERS} supported. Widen these fields to "
                f"unsigned short in the schema before exporting this many."
            )
            return

        warnings = []
        for c in self.countries:
            pol = self.politics.get(c['id'], self.default_politics())
            if sum(pol['support']) != 100:
                warnings.append(f"{c['name']}: support sums to {sum(pol['support'])}, not 100")
            if pol['current_leader'][pol['ruling']] is None:
                warnings.append(f"{c['name']}: ruling ideology ({IDEOLOGIES[pol['ruling']]}) has no active leader")

        if warnings:
            proceed = messagebox.askyesno(
                "Warnings found",
                f"{len(warnings)} issue(s) found:\n\n"
                + "\n".join(warnings[:12]) + ("\n..." if len(warnings) > 12 else "")
                + "\n\nExport anyway?"
            )
            if not proceed:
                return

        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return

        try:
            country_count = len(self.countries)
            country_name_by_id = {c['id']: c['name'] for c in self.countries}

            # Stable export order for leaders[] — creation order. This order (and therefore
            # each leader's ARRAY INDEX) can shift between exports as leaders are added/deleted;
            # portrait_id does NOT shift, since it's the leader's original stable id, stored
            # explicitly as its own field rather than derived from this order.
            sorted_leader_ids = sorted(self.leaders.keys())
            leader_array_index = {lid: idx for idx, lid in enumerate(sorted_leader_ids)}
            leader_count = len(sorted_leader_ids)

            # ---- political_data.h ----
            with open(f"{output_dir}/political_data.h", 'w', encoding='utf-8') as f:
                f.write("#ifndef POLITICAL_DATA_H\n")
                f.write("#define POLITICAL_DATA_H\n\n")
                f.write("// Keep in sync with IDEOLOGIES[] in political_editor.py\n")
                f.write("typedef enum {\n")
                for i, ideo in enumerate(IDEOLOGIES):
                    comma = ',' if i < IDEOLOGY_COUNT - 1 else ''
                    f.write(f"    IDEOLOGY_{ideo.upper()} = {i}{comma}\n")
                f.write("} Ideology;\n\n")
                f.write(f"#define IDEOLOGY_COUNT {IDEOLOGY_COUNT}\n\n")

                f.write("#define LEADER_NONE 0xFF // sentinel: no leader currently active for this ideology slot\n\n")

                f.write("typedef struct {\n")
                f.write("    const char*   name;\n")
                f.write("    unsigned char country_id;   // which country this leader belongs to\n")
                f.write("    unsigned char ideology;     // which ideology they represent\n")
                f.write("    unsigned char portrait_id;  // stable across re-exports — NOT this leader's index below,\n")
                f.write("                                // which can shift as the roster changes\n")
                f.write("} Leader;\n\n")

                f.write(f"#define LEADER_COUNT {leader_count}\n\n")
                f.write("extern const Leader leaders[LEADER_COUNT];\n\n")

                f.write("typedef struct {\n")
                f.write("    unsigned char ideology_support[IDEOLOGY_COUNT]; // percentages, should sum to 100\n")
                f.write("    unsigned char ruling_ideology;                  // index into Ideology — not necessarily the most popular\n")
                f.write("    unsigned char stability;                        // 0-100\n")
                f.write("    unsigned char current_leader[IDEOLOGY_COUNT];   // index into leaders[], or LEADER_NONE\n")
                f.write("} CountryPolitics;\n\n")

                f.write(f"#define COUNTRY_POLITICS_COUNT {country_count}\n\n")
                f.write("extern const CountryPolitics country_politics[COUNTRY_POLITICS_COUNT];\n\n")
                f.write("#endif\n")

            # ---- political_data.c ----
            with open(f"{output_dir}/political_data.c", 'w', encoding='utf-8') as f:
                f.write("#include \"political_data.h\"\n\n")

                f.write("const Leader leaders[LEADER_COUNT] = {\n")
                for idx, lid in enumerate(sorted_leader_ids):
                    leader   = self.leaders[lid]
                    name     = leader['name'].replace('\\', '\\\\').replace('"', '\\"')
                    cname    = country_name_by_id.get(leader['country_id'], '?')
                    ideo_name = IDEOLOGIES[leader['ideology']]
                    comma    = ',' if idx < leader_count - 1 else ''
                    f.write(f'    {{"{name}", {leader["country_id"]}, {leader["ideology"]}, {lid}}}{comma}'
                            f'  // {cname} - {ideo_name}\n')
                f.write("};\n\n")

                f.write("const CountryPolitics country_politics[COUNTRY_POLITICS_COUNT] = {\n")
                for c in self.countries:
                    cid = c['id']
                    pol = self.politics.get(cid, self.default_politics())

                    support_braces = "{" + ", ".join(str(v) for v in pol['support']) + "}"

                    cur_leader_vals = []
                    for lid in pol['current_leader']:
                        cur_leader_vals.append(str(leader_array_index[lid]) if lid in leader_array_index else "LEADER_NONE")
                    current_leader_braces = "{" + ", ".join(cur_leader_vals) + "}"

                    comma = ',' if cid < country_count - 1 else ''
                    f.write(f'    // {c["name"]}\n')
                    f.write(f'    {{{support_braces}, {pol["ruling"]}, {pol["stability"]}, {current_leader_braces}}}{comma}\n')
                f.write("};\n")

            # ---- portraits_manifest.csv ----
            manifest_path = f"{output_dir}/portraits_manifest.csv"
            with open(manifest_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["PortraitID", "CountryID", "CountryName", "Ideology", "LeaderName", "CurrentlyActive"])
                for lid in sorted_leader_ids:
                    leader = self.leaders[lid]
                    pol    = self.politics.get(leader['country_id'], self.default_politics())
                    active = "yes" if pol['current_leader'][leader['ideology']] == lid else "no"
                    writer.writerow([
                        lid, leader['country_id'], country_name_by_id.get(leader['country_id'], '?'),
                        IDEOLOGIES[leader['ideology']], leader['name'], active
                    ])

            messagebox.showinfo(
                "Export Complete",
                f"Exported to {output_dir}\n\n"
                f"- political_data.h/c ({country_count} countries, {leader_count} leaders)\n"
                f"- portraits_manifest.csv ({leader_count} leader portraits)"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("980x800")
    app = PoliticalEditor(root)
    root.mainloop()