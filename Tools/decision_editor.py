"""
Decision Editor — author tool for Pocket Wars

Build country decisions: a title (scrollable decision list), flavor text +
effect summary (shown on the top screen when selected), and TWO INDEPENDENT
condition trees:

  - VISIBILITY   — must be true for the decision to appear in the list at all
  - AVAILABILITY — must be true to actually be TAKEABLE. Game code can still
                   show it greyed-out if visible-but-locked. Only this tree's
                   auto-generated prerequisites_text is meant to be shown to
                   the player — visibility conditions stay hidden.

Two ways to build a condition tree:
  1. Click UI — Add AND/OR/NOT group, Add Condition (a parameterized leaf),
     Add Saved Condition (a reference to a named/reusable condition).
  2. Query bar — type an expression combining SAVED CONDITION NAMES with
     AND / OR / NOT / parentheses (space = implicit AND, like a tag search:
     "CZECH_STATES AND -AT_WAR"). Raw parameterized leaves aren't typeable
     directly — save them once via the click UI, give them a name, then
     they're reusable both here and by reference in other trees.

NAMED CONDITIONS are a separate library (Manage Named Conditions... button),
editable with the exact same tree UI. They can reference each other (cycle
detection included) — e.g. build "CZECH_STATES" once as an OR of several
CONTROLS_PROVINCE leaves, then reuse it everywhere as a single tag.

"CONTROLS_PROVINCE" IS your "controls a state" check — your shipped game
data only has province-level ownership, province and state are the same
concept here, nothing renamed.

COOLDOWN: a decision is either ONCE ONLY (a hard sentinel, never retakeable)
or repeatable after N turns.

DECISION_TAKEN is a condition leaf referencing any decision (including
itself) — true if ANY country has ever taken it. Wrap in NOT for "no one
else has done this yet". Requires a runtime `bool decision_taken[]` global,
not built yet.

EXPORT FORMAT: condition trees compile to POSTFIX (RPN) instructions, not
literal tree structures — a small stack-machine loop in game code (built
later) evaluates them with no recursion, no pointers. Both condition and
effect instructions live in shared flat pools; each Decision references its
slice via offset+length, same pattern as leaders[] in political_data.h.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import re

IDEOLOGIES = ["Fascism", "Democracy", "Communism", "Autocracy"]
IDEOLOGY_COUNT = len(IDEOLOGIES)

EFFECT_COUNTRY_SELF = -1   # sentinel: "whichever country took this decision"
DECISION_ONCE_ONLY = -1    # sentinel: cooldown_turns value meaning "never repeatable"

# ----------------------------------------------------------------------
# CONDITION / EFFECT REGISTRIES
# Add a new entry here + one export-side case to extend either system.
# ----------------------------------------------------------------------

CONDITION_TYPES = {
    'COUNTRY_IS':         {'label': 'Country is...',                          'params': [('country_id', 'country')]},
    'STABILITY_GE':       {'label': 'Stability >=',                           'params': [('value', 'percent')]},
    'STABILITY_LE':       {'label': 'Stability <=',                           'params': [('value', 'percent')]},
    'SUPPORT_GE':         {'label': 'Ideology support >=',                    'params': [('ideology', 'ideology'), ('value', 'percent')]},
    'SUPPORT_LE':         {'label': 'Ideology support <=',                    'params': [('ideology', 'ideology'), ('value', 'percent')]},
    'RULING_IS':          {'label': 'Ruling ideology is...',                  'params': [('ideology', 'ideology')]},
    'CONTROLS_PROVINCE':  {'label': 'Controls province/state...',             'params': [('province_id', 'province')]},
    'DECISION_TAKEN':     {'label': 'Decision has been taken by any country...', 'params': [('decision_id', 'decision')]},
}

EFFECT_TYPES = {
    'ADD_STABILITY':        {'label': 'Add to stability (acting country)',          'params': [('delta', 'delta_percent')]},
    'ADD_SUPPORT':           {'label': 'Add to ideology support (acting country)',   'params': [('ideology', 'ideology'), ('delta', 'delta_percent')]},
    'SET_RULING_IDEOLOGY':   {'label': 'Set ruling ideology (acting country)',       'params': [('ideology', 'ideology')]},
    'SET_PROVINCE_OWNER':    {'label': 'Set province/state owner',                   'params': [('province_id', 'province'), ('country_id', 'country_or_self')]},
    'SET_LEADER':            {'label': 'Set ideology leader to a specific person',   'params': [('leader', 'leader')]},
    'CLEAR_LEADER':          {'label': 'Clear ideology leader (power vacuum)',       'params': [('country_id', 'country_or_self'), ('ideology', 'ideology')]},
    'FORM_NATION':           {'label': 'Form nation — acting country transforms into...', 'params': [('formed_country', 'country')]},
    'ABSORB_COUNTRY':        {'label': "Absorb another country's provinces",         'params': [('absorbed_country', 'country'), ('into_country', 'country_or_self')]},
    'ADD_CORE':              {'label': 'Grant a core on a province',                 'params': [('province_id', 'province'), ('country_id', 'country_or_self')]},
}

CONDOP_ORDER = ['AND', 'OR', 'NOT'] + list(CONDITION_TYPES.keys())
EFFECTOP_ORDER = list(EFFECT_TYPES.keys())


# ----------------------------------------------------------------------
# TREE CONTEXT — bundles a Treeview + get/set root closures, so the same
# editing logic works for decision visibility/availability AND for named
# (saved/reusable) conditions without duplicating it.
# ----------------------------------------------------------------------

class TreeContext:
    def __init__(self, tree_widget, get_root, set_root):
        self.tree_widget = tree_widget
        self.get_root = get_root
        self.set_root = set_root
        self.item_nodes = {}


def pick_from_list(parent, title_text, options):
    if not options:
        messagebox.showinfo(title_text, "No saved conditions yet — create one first via 'Manage Named Conditions...'")
        return None
    win = tk.Toplevel(parent)
    win.title(title_text)
    win.transient(parent)
    win.grab_set()
    lb = tk.Listbox(win, height=min(15, len(options)))
    for o in options:
        lb.insert(tk.END, o)
    lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    result = {'value': None}
    def on_ok():
        sel = lb.curselection()
        if sel:
            result['value'] = options[sel[0]]
        win.destroy()
    btns = ttk.Frame(win)
    btns.pack(pady=(0, 8))
    ttk.Button(btns, text="OK", command=on_ok).pack(side=tk.LEFT, padx=4)
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=4)
    lb.bind('<Double-Button-1>', lambda e: on_ok())
    parent.wait_window(win)
    return result['value']


class DecisionEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Decision Editor")

        self.countries = []        # [{'id','name'}, ...] — read-only, from countries.c
        self.provinces = {}        # province_id -> name (optional, from province_data.c)
        self.leaders = []          # [{'name','country_id','ideology','portrait_id'}, ...] — from political_data.c
        self.decisions = {}        # decision_id -> decision dict
        self.next_decision_id = 0
        self.named_conditions = {} # name(str, UPPERCASE) -> tree node

        self.active_id = None
        self.active_named_name = None
        self._loading_form = False

        self.setup_gui()

    # ------------------------------------------------------------------
    # PARSERS (read-only reference data)
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
            raise ValueError("Found the countries array but couldn't parse any entries")
        return [{'id': i, 'name': name} for i, name in enumerate(names)]

    def parse_province_data_c(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'Province\s+provinces\[.*?\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
        if not match:
            raise ValueError("Could not find provinces array in province_data.c")
        pattern = r'\{\s*"([^"]*)"\s*,\s*0x[0-9A-Fa-f]+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\}'
        names = re.findall(pattern, match.group(1))
        if not names:
            raise ValueError("Found the provinces array but couldn't parse any entries")
        return {i: name for i, name in enumerate(names)}

    def parse_leaders_from_political_data(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'const Leader leaders\[LEADER_COUNT\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
        if not match:
            raise ValueError("Could not find leaders array in political_data.c")
        pattern = r'\{\s*"([^"]*)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}'
        entries = re.findall(pattern, match.group(1))
        if not entries:
            raise ValueError("Found the leaders array but couldn't parse any entries")
        return [{'name': n, 'country_id': int(cid), 'ideology': int(ideo), 'portrait_id': int(pid)}
                for n, cid, ideo, pid in entries]

    # ------------------------------------------------------------------
    # DATA HELPERS
    # ------------------------------------------------------------------

    def default_decision(self):
        return {
            'title': 'New Decision',
            'flavor_text': '',
            'effect_text': '',
            'prerequisites_text': '',
            'once_only': True,
            'cooldown_turns': 0,
            'visibility': None,
            'availability': None,
            'effects': [],
        }

    def ensure_decision_defaults(self, d):
        for k, v in self.default_decision().items():
            if k not in d:
                d[k] = v
        return d

    def country_name(self, cid):
        for c in self.countries:
            if c['id'] == cid:
                return c['name']
        return f"country#{cid}"

    def decision_title(self, did):
        if did in self.decisions:
            return self.decisions[did]['title']
        return f"#{did} (unknown)"

    def find_leader(self, portrait_id):
        return next((l for l in self.leaders if l['portrait_id'] == portrait_id), None)

    def leader_display_name(self, l):
        return f"{l['name']} ({self.country_name(l['country_id'])}, {IDEOLOGIES[l['ideology']]})"

    def describe_leaf(self, node):
        ctype = node['condition']
        p = node['params']
        if ctype == 'COUNTRY_IS':
            return f"Country is {self.country_name(p.get('country_id', 0))}"
        if ctype in ('STABILITY_GE', 'STABILITY_LE'):
            op = '>=' if ctype == 'STABILITY_GE' else '<='
            return f"Stability {op} {p.get('value', 0)}%"
        if ctype in ('SUPPORT_GE', 'SUPPORT_LE'):
            op = '>=' if ctype == 'SUPPORT_GE' else '<='
            return f"{IDEOLOGIES[p.get('ideology', 0)]} support {op} {p.get('value', 0)}%"
        if ctype == 'RULING_IS':
            return f"Ruling ideology is {IDEOLOGIES[p.get('ideology', 0)]}"
        if ctype == 'CONTROLS_PROVINCE':
            pid = p.get('province_id', 0)
            pname = self.provinces.get(pid, '')
            return f"Controls province #{pid}" + (f" ({pname})" if pname else "")
        if ctype == 'DECISION_TAKEN':
            return f"Decision '{self.decision_title(p.get('decision_id', -1))}' taken by any country"
        return CONDITION_TYPES[ctype]['label']

    def describe_effect(self, eff):
        etype = eff['effect']
        p = eff['params']
        if etype == 'ADD_STABILITY':
            return f"Stability {p.get('delta', 0):+d}"
        if etype == 'ADD_SUPPORT':
            return f"{IDEOLOGIES[p.get('ideology', 0)]} support {p.get('delta', 0):+d}"
        if etype == 'SET_RULING_IDEOLOGY':
            return f"Set ruling ideology to {IDEOLOGIES[p.get('ideology', 0)]}"
        if etype == 'SET_PROVINCE_OWNER':
            pid = p.get('province_id', 0)
            pname = self.provinces.get(pid, '')
            cid = p.get('country_id', EFFECT_COUNTRY_SELF)
            target = "SELF (acting country)" if cid == EFFECT_COUNTRY_SELF else self.country_name(cid)
            return f"Give province #{pid}" + (f" ({pname})" if pname else "") + f" to {target}"
        if etype == 'SET_LEADER':
            leader = self.find_leader(p.get('leader', -1))
            if leader:
                return f"Set {IDEOLOGIES[leader['ideology']]} leader ({self.country_name(leader['country_id'])}) to {leader['name']}"
            return f"Set leader to #{p.get('leader', -1)} (unknown — reload political_data.c?)"
        if etype == 'CLEAR_LEADER':
            cid = p.get('country_id', EFFECT_COUNTRY_SELF)
            target = "SELF (acting country)" if cid == EFFECT_COUNTRY_SELF else self.country_name(cid)
            return f"Clear {IDEOLOGIES[p.get('ideology', 0)]} leader for {target} (power vacuum)"
        if etype == 'FORM_NATION':
            return f"Transform acting country into {self.country_name(p.get('formed_country', 0))} (transfers own provinces + political state, deactivates old identity)"
        if etype == 'ABSORB_COUNTRY':
            absorbed = self.country_name(p.get('absorbed_country', 0))
            cid = p.get('into_country', EFFECT_COUNTRY_SELF)
            target = "SELF (acting country)" if cid == EFFECT_COUNTRY_SELF else self.country_name(cid)
            return f"Absorb {absorbed}'s provinces into {target} — {absorbed} ceases to exist"
        if etype == 'ADD_CORE':
            pid = p.get('province_id', 0)
            pname = self.provinces.get(pid, '')
            cid = p.get('country_id', EFFECT_COUNTRY_SELF)
            target = "SELF (acting country)" if cid == EFFECT_COUNTRY_SELF else self.country_name(cid)
            return f"Grant core on province #{pid}" + (f" ({pname})" if pname else "") + f" to {target}"
        return etype

    def describe_tree(self, node):
        if node is None:
            return "(always true)"
        if node['type'] == 'LEAF':
            return self.describe_leaf(node)
        if node['type'] == 'REF':
            return node['name']
        if node['type'] == 'NOT':
            return f"NOT ({self.describe_tree(node['children'][0])})"
        joiner = ' AND ' if node['type'] == 'AND' else ' OR '
        return '(' + joiner.join(self.describe_tree(c) for c in node['children']) + ')'

    # ------------------------------------------------------------------
    # GUI SETUP
    # ------------------------------------------------------------------

    def setup_gui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main, width=280)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)

        ttk.Label(left, text="Decisions", font=('Arial', 12, 'bold')).pack(pady=5)
        self.decision_listbox = tk.Listbox(left, height=22)
        self.decision_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.decision_listbox.bind('<<ListboxSelect>>', self.on_decision_select)

        ttk.Button(left, text="Add Decision", command=self.add_decision).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Duplicate Selected", command=self.duplicate_decision).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Delete Selected", command=self.delete_decision).pack(fill=tk.X, pady=2)

        ttk.Separator(left, orient='horizontal').pack(fill=tk.X, pady=6)
        ttk.Button(left, text="Manage Named Conditions...", command=self.open_named_conditions_manager).pack(fill=tk.X, pady=2)

        ttk.Separator(left, orient='horizontal').pack(fill=tk.X, pady=6)
        ttk.Button(left, text="Load countries.c (required)", command=self.load_countries).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Load province_data.c (optional)", command=self.load_provinces).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Load political_data.c (for leaders)", command=self.load_leaders).pack(fill=tk.X, pady=2)

        ttk.Separator(left, orient='horizontal').pack(fill=tk.X, pady=6)
        ttk.Button(left, text="Save Project", command=self.save_project).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Load Project", command=self.load_project).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Export to C", command=self.export_to_c).pack(fill=tk.X, pady=2)

        self.status_label = ttk.Label(self.root, text="Load countries.c first, then add a decision.", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.form_title = ttk.Label(right, text="No decision selected", font=('Arial', 13, 'bold'))
        self.form_title.pack(anchor=tk.W, pady=(0, 8))

        notebook = ttk.Notebook(right)
        notebook.pack(fill=tk.BOTH, expand=True)

        # --- Basic Info ---
        info_tab = ttk.Frame(notebook, padding=8)
        notebook.add(info_tab, text="Basic Info")

        ttk.Label(info_tab, text="Title (shown in the decision list):").pack(anchor=tk.W)
        self.title_var = tk.StringVar()
        te = ttk.Entry(info_tab, textvariable=self.title_var)
        te.pack(fill=tk.X, pady=(0, 8))
        te.bind('<KeyRelease>', lambda e: self.on_field_change())

        ttk.Label(info_tab, text="Flavor text (top screen when selected):").pack(anchor=tk.W)
        self.flavor_text = tk.Text(info_tab, height=5, wrap=tk.WORD)
        self.flavor_text.pack(fill=tk.X, pady=(0, 8))
        self.flavor_text.bind('<KeyRelease>', lambda e: self.on_field_change())

        ttk.Label(info_tab, text="Effect summary (human-authored):").pack(anchor=tk.W)
        self.effect_text = tk.Text(info_tab, height=3, wrap=tk.WORD)
        self.effect_text.pack(fill=tk.X, pady=(0, 8))
        self.effect_text.bind('<KeyRelease>', lambda e: self.on_field_change())

        cd_frame = ttk.LabelFrame(info_tab, text="Repeatability", padding=8)
        cd_frame.pack(fill=tk.X, pady=(0, 8))
        self.once_only_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(cd_frame, text="Once only — can never be taken again after being taken",
                        variable=self.once_only_var, value=True, command=self.on_field_change).pack(anchor=tk.W)
        cd_row = ttk.Frame(cd_frame)
        cd_row.pack(anchor=tk.W, fill=tk.X)
        ttk.Radiobutton(cd_row, text="Repeatable — cooldown (turns):",
                        variable=self.once_only_var, value=False, command=self.on_field_change).pack(side=tk.LEFT)
        self.cooldown_var = tk.IntVar(value=10)
        cd_spin = ttk.Spinbox(cd_row, from_=0, to=999, width=6, textvariable=self.cooldown_var, command=self.on_field_change)
        cd_spin.pack(side=tk.LEFT, padx=6)
        cd_spin.bind('<KeyRelease>', lambda e: self.on_field_change())

        # --- Visibility tab ---
        vis_tab = ttk.Frame(notebook, padding=8)
        notebook.add(vis_tab, text="Visibility Conditions")
        ttk.Label(vis_tab, text="Must be TRUE for this decision to appear in the list at all. Never shown to the player.",
                  foreground="#555").pack(anchor=tk.W, pady=(0, 6))
        self.vis_ctx = TreeContext(
            tree_widget=None,
            get_root=lambda: self.decisions[self.active_id]['visibility'],
            set_root=lambda n: self.decisions[self.active_id].__setitem__('visibility', n),
        )
        self.vis_ctx.tree_widget = self.build_condition_tab(vis_tab, self.vis_ctx)

        # --- Availability tab ---
        avail_tab = ttk.Frame(notebook, padding=8)
        notebook.add(avail_tab, text="Availability Conditions")
        ttk.Label(avail_tab, text="Must be TRUE for the decision to be TAKEABLE (can be visible-but-locked). "
                                   "This tree's text below IS shown to the player as prerequisites.",
                  foreground="#555").pack(anchor=tk.W, pady=(0, 6))
        self.avail_ctx = TreeContext(
            tree_widget=None,
            get_root=lambda: self.decisions[self.active_id]['availability'],
            set_root=lambda n: self.decisions[self.active_id].__setitem__('availability', n),
        )
        self.avail_ctx.tree_widget = self.build_condition_tab(avail_tab, self.avail_ctx)

        ttk.Separator(avail_tab, orient='horizontal').pack(fill=tk.X, pady=8)
        ttk.Label(avail_tab, text="Prerequisites text (shown to player — auto-generated, editable):").pack(anchor=tk.W)
        self.prereq_text = tk.Text(avail_tab, height=3, wrap=tk.WORD)
        self.prereq_text.pack(fill=tk.X, pady=(0, 4))
        self.prereq_text.bind('<KeyRelease>', lambda e: self.on_field_change())
        ttk.Button(avail_tab, text="Regenerate from Availability Conditions",
                   command=self.regenerate_prerequisites_text).pack(anchor=tk.W)

        # --- Effects tab ---
        effects_tab = ttk.Frame(notebook, padding=8)
        notebook.add(effects_tab, text="Effects")
        ttk.Label(effects_tab, text="Applied in order, unconditionally, when the decision is taken.",
                  foreground="#555").pack(anchor=tk.W, pady=(0, 6))

        eff_body = ttk.Frame(effects_tab)
        eff_body.pack(fill=tk.BOTH, expand=True)
        self.effects_listbox = tk.Listbox(eff_body, height=14)
        self.effects_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.effects_listbox.bind('<Double-Button-1>', lambda e: self.edit_effect())

        eff_btns = ttk.Frame(eff_body)
        eff_btns.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(eff_btns, text="Add Effect", width=14, command=self.add_effect).pack(pady=2)
        ttk.Button(eff_btns, text="Edit Selected", width=14, command=self.edit_effect).pack(pady=2)
        ttk.Button(eff_btns, text="Delete Selected", width=14, command=self.delete_effect).pack(pady=2)
        ttk.Button(eff_btns, text="Move Up", width=14, command=lambda: self.move_effect(-1)).pack(pady=2)
        ttk.Button(eff_btns, text="Move Down", width=14, command=lambda: self.move_effect(1)).pack(pady=2)

    def build_condition_tab(self, parent, ctx):
        query_row = ttk.Frame(parent)
        query_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(query_row, text="Quick entry:").pack(side=tk.LEFT)
        query_entry = ttk.Entry(query_row)
        query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(query_row, text="Apply Query", command=lambda: self.apply_query(ctx, query_entry)).pack(side=tk.LEFT)

        tree = ttk.Treeview(parent, show='tree', height=12)
        tree.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        tree.bind('<Double-Button-1>', lambda e: self.on_tree_double_click(ctx))

        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Add AND",     command=lambda: self.add_group(ctx, 'AND')).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Add OR",      command=lambda: self.add_group(ctx, 'OR')).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Add NOT",     command=lambda: self.add_group(ctx, 'NOT')).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Add Condition", command=lambda: self.add_leaf(ctx)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Add Saved Condition", command=lambda: self.add_ref(ctx)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Delete Selected", command=lambda: self.delete_node(ctx)).pack(side=tk.LEFT, padx=2)

        return tree

    # ------------------------------------------------------------------
    # LOAD REFERENCE DATA
    # ------------------------------------------------------------------

    def load_countries(self):
        fp = filedialog.askopenfilename(title="Select countries.c", filetypes=[("C source", "*.c"), ("All files", "*.*")])
        if not fp:
            return
        try:
            self.countries = self.parse_countries_c(fp)
            self.status_label.config(text=f"Loaded {len(self.countries)} countries")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load countries.c: {e}")

    def load_provinces(self):
        fp = filedialog.askopenfilename(title="Select province_data.c", filetypes=[("C source", "*.c"), ("All files", "*.*")])
        if not fp:
            return
        try:
            self.provinces = self.parse_province_data_c(fp)
            self.status_label.config(text=f"Loaded {len(self.provinces)} province names")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load province_data.c: {e}")

    def load_leaders(self):
        fp = filedialog.askopenfilename(title="Select political_data.c", filetypes=[("C source", "*.c"), ("All files", "*.*")])
        if not fp:
            return
        try:
            self.leaders = self.parse_leaders_from_political_data(fp)
            self.status_label.config(text=f"Loaded {len(self.leaders)} leaders")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load political_data.c: {e}")

    # ------------------------------------------------------------------
    # DECISION LIST
    # ------------------------------------------------------------------

    def refresh_decision_list(self):
        self.decision_listbox.delete(0, tk.END)
        for did in sorted(self.decisions.keys()):
            d = self.decisions[did]
            tags = []
            if d['visibility'] is not None: tags.append('V')
            if d['availability'] is not None: tags.append('A')
            if d['effects']: tags.append(f"{len(d['effects'])}fx")
            tags.append("ONCE" if d['once_only'] else f"CD{d['cooldown_turns']}")
            self.decision_listbox.insert(tk.END, f"{d['title']}  [{' '.join(tags)}]")

    def _decision_id_from_index(self, idx):
        return sorted(self.decisions.keys())[idx]

    def add_decision(self):
        if not self.countries:
            messagebox.showwarning("Load countries first", "Load countries.c before creating decisions")
            return
        did = self.next_decision_id
        self.next_decision_id += 1
        self.decisions[did] = self.default_decision()
        self.refresh_decision_list()
        self.active_id = did
        self.load_form_from_active()

    def duplicate_decision(self):
        sel = self.decision_listbox.curselection()
        if not sel:
            messagebox.showwarning("No selection", "Select a decision to duplicate first")
            return
        src_id = self._decision_id_from_index(sel[0])
        new_id = self.next_decision_id
        self.next_decision_id += 1
        self.decisions[new_id] = json.loads(json.dumps(self.decisions[src_id]))
        self.decisions[new_id]['title'] += " (copy)"
        self.refresh_decision_list()
        self.active_id = new_id
        self.load_form_from_active()

    def delete_decision(self):
        sel = self.decision_listbox.curselection()
        if not sel:
            messagebox.showwarning("No selection", "Select a decision to delete first")
            return
        did = self._decision_id_from_index(sel[0])
        if not messagebox.askyesno("Confirm Delete", f"Delete decision '{self.decisions[did]['title']}'? "
                                                       f"Note: any DECISION_TAKEN references to it elsewhere will break."):
            return
        del self.decisions[did]
        self.active_id = None
        self.form_title.config(text="No decision selected")
        self.refresh_decision_list()

    def on_decision_select(self, event):
        sel = self.decision_listbox.curselection()
        if not sel:
            return
        self.commit_form_to_active()
        self.active_id = self._decision_id_from_index(sel[0])
        self.load_form_from_active()

    # ------------------------------------------------------------------
    # FORM <-> DATA
    # ------------------------------------------------------------------

    def load_form_from_active(self):
        if self.active_id is None:
            return
        d = self.decisions[self.active_id]

        self._loading_form = True
        self.form_title.config(text=d['title'])
        self.title_var.set(d['title'])
        self.flavor_text.delete('1.0', tk.END); self.flavor_text.insert('1.0', d['flavor_text'])
        self.effect_text.delete('1.0', tk.END); self.effect_text.insert('1.0', d['effect_text'])
        self.prereq_text.delete('1.0', tk.END); self.prereq_text.insert('1.0', d['prerequisites_text'])
        self.once_only_var.set(d['once_only'])
        self.cooldown_var.set(d['cooldown_turns'])
        self._loading_form = False

        self.refresh_condition_tree(self.vis_ctx)
        self.refresh_condition_tree(self.avail_ctx)
        self.refresh_effects_list()

    def commit_form_to_active(self):
        if self.active_id is None:
            return
        d = self.decisions[self.active_id]
        d['title'] = self.title_var.get()
        d['flavor_text'] = self.flavor_text.get('1.0', 'end-1c')
        d['effect_text'] = self.effect_text.get('1.0', 'end-1c')
        d['prerequisites_text'] = self.prereq_text.get('1.0', 'end-1c')
        d['once_only'] = bool(self.once_only_var.get())
        try:
            d['cooldown_turns'] = int(self.cooldown_var.get())
        except (ValueError, tk.TclError):
            d['cooldown_turns'] = 0

    def on_field_change(self):
        if self._loading_form:
            return
        self.commit_form_to_active()
        self.form_title.config(text=self.title_var.get())
        self.refresh_decision_list()

    def regenerate_prerequisites_text(self):
        if self.active_id is None:
            return
        text = self.describe_tree(self.decisions[self.active_id]['availability'])
        self.prereq_text.delete('1.0', tk.END)
        self.prereq_text.insert('1.0', text)
        self.on_field_change()

    # ------------------------------------------------------------------
    # CONDITION TREE EDITING (generic — works for decisions AND named conditions)
    # ------------------------------------------------------------------

    def refresh_condition_tree(self, ctx):
        tree = ctx.tree_widget
        tree.delete(*tree.get_children())
        ctx.item_nodes.clear()
        root = ctx.get_root()
        if root is not None:
            self._insert_tree_items(ctx, '', root)

    def _insert_tree_items(self, ctx, parent_item, node):
        if node['type'] == 'LEAF':
            label = self.describe_leaf(node)
        elif node['type'] == 'REF':
            label = f"[TAG] {node['name']}"
        else:
            label = node['type']
        item_id = ctx.tree_widget.insert(parent_item, 'end', text=label, open=True)
        ctx.item_nodes[item_id] = node
        if node['type'] in ('AND', 'OR', 'NOT'):
            for child in node['children']:
                self._insert_tree_items(ctx, item_id, child)

    def _attach_node(self, ctx, new_node):
        """Places new_node at the tree root, or as a child of the selected group node."""
        sel = ctx.tree_widget.selection()
        if not sel:
            if ctx.get_root() is not None:
                messagebox.showwarning("Root exists", "This tree already has a root — select a group node to add under, or delete the root first")
                return False
            ctx.set_root(new_node)
        else:
            parent_node = ctx.item_nodes[sel[0]]
            if parent_node['type'] in ('LEAF', 'REF'):
                messagebox.showwarning("Can't nest here", "Select an AND/OR/NOT group, or nothing to create a root")
                return False
            if parent_node['type'] == 'NOT' and len(parent_node['children']) >= 1:
                messagebox.showwarning("NOT is full", "A NOT group can only have one child")
                return False
            parent_node['children'].append(new_node)
        return True

    def add_group(self, ctx, group_type):
        if not self._require_active_context(ctx):
            return
        if self._attach_node(ctx, {'type': group_type, 'children': []}):
            self.refresh_condition_tree(ctx)
            self.refresh_decision_list()

    def add_leaf(self, ctx):
        if not self._require_active_context(ctx):
            return
        if not self.countries:
            messagebox.showwarning("Load countries first", "Load countries.c before adding conditions")
            return
        dialog = LeafConditionDialog(self.root, self.countries, self.provinces, self.decisions, self.active_id_for_context(ctx))
        if dialog.result_data is None:
            return
        if self._attach_node(ctx, dialog.result_data):
            self.refresh_condition_tree(ctx)
            self.refresh_decision_list()

    def add_ref(self, ctx):
        if not self._require_active_context(ctx):
            return
        chosen = pick_from_list(self.root, "Add Saved Condition", sorted(self.named_conditions.keys()))
        if chosen is None:
            return
        if self._attach_node(ctx, {'type': 'REF', 'name': chosen}):
            self.refresh_condition_tree(ctx)
            self.refresh_decision_list()

    def on_tree_double_click(self, ctx):
        sel = ctx.tree_widget.selection()
        if not sel:
            return
        node = ctx.item_nodes[sel[0]]
        if node['type'] == 'LEAF':
            self.edit_leaf(ctx)
        elif node['type'] == 'REF':
            if messagebox.askyesno("Saved condition", f"This is a reference to saved condition '{node['name']}'. Open it for editing?"):
                self.open_named_conditions_manager(preselect=node['name'])

    def edit_leaf(self, ctx):
        sel = ctx.tree_widget.selection()
        if not sel:
            return
        node = ctx.item_nodes[sel[0]]
        if node['type'] != 'LEAF':
            return
        dialog = LeafConditionDialog(self.root, self.countries, self.provinces, self.decisions,
                                      self.active_id_for_context(ctx), initial=node)
        if dialog.result_data is None:
            return
        node['condition'] = dialog.result_data['condition']
        node['params'] = dialog.result_data['params']
        self.refresh_condition_tree(ctx)

    def delete_node(self, ctx):
        sel = ctx.tree_widget.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select a node to delete")
            return
        target = ctx.item_nodes[sel[0]]
        if ctx.get_root() is target:
            ctx.set_root(None)
        else:
            self._remove_child(ctx.get_root(), target)
        self.refresh_condition_tree(ctx)
        self.refresh_decision_list()

    def _remove_child(self, node, target):
        # Identity-based (`is`), not structural equality — two identical
        # leaves must not be confused with each other.
        if node is None or node['type'] in ('LEAF', 'REF'):
            return
        for i, c in enumerate(node['children']):
            if c is target:
                del node['children'][i]
                return
            self._remove_child(c, target)

    def _require_active_context(self, ctx):
        if ctx in (self.vis_ctx, self.avail_ctx) and self.active_id is None:
            messagebox.showwarning("No decision selected", "Select a decision first")
            return False
        if ctx not in (self.vis_ctx, self.avail_ctx) and self.active_named_name is None:
            messagebox.showwarning("No saved condition selected", "Select or create a saved condition first")
            return False
        return True

    def active_id_for_context(self, ctx):
        """Only meaningful for decision contexts — lets the 'decision' leaf param label self-references."""
        return self.active_id if ctx in (self.vis_ctx, self.avail_ctx) else None

    def apply_query(self, ctx, entry_widget):
        text = entry_widget.get().strip()
        if not text:
            return
        try:
            tree = self.parse_named_query(text)
        except ValueError as e:
            messagebox.showerror("Query error", str(e))
            return
        if not self._require_active_context(ctx):
            return
        if ctx.get_root() is not None:
            if not messagebox.askyesno("Replace tree?", "This replaces the current condition tree with the parsed query. Continue?"):
                return
        ctx.set_root(tree)
        self.refresh_condition_tree(ctx)
        self.refresh_decision_list()

    # ------------------------------------------------------------------
    # QUERY PARSER — "TAG1 AND (TAG2 OR -TAG3)" style, tags = named conditions
    # ------------------------------------------------------------------

    def tokenize_query(self, text):
        return re.findall(r'\(|\)|~|-|[A-Za-z_][A-Za-z0-9_]*', text)

    def parse_named_query(self, text):
        tokens = self.tokenize_query(text)
        if not tokens:
            raise ValueError("Empty query")
        pos = [0]

        def peek():
            return tokens[pos[0]] if pos[0] < len(tokens) else None
        def consume():
            t = tokens[pos[0]]; pos[0] += 1; return t
        def is_primary_start(t):
            return t is not None and t != ')' and t != '~' and t.upper() != 'OR'

        def parse_or():
            left = parse_and()
            while peek() is not None and (peek().upper() == 'OR' or peek() == '~'):
                consume()
                left = {'type': 'OR', 'children': [left, parse_and()]}
            return left

        def parse_and():
            left = parse_not()
            while True:
                t = peek()
                if not is_primary_start(t):
                    break
                if t.upper() == 'AND':
                    consume()
                left = {'type': 'AND', 'children': [left, parse_not()]}
            return left

        def parse_not():
            if peek() is not None and (peek().upper() == 'NOT' or peek() == '-'):
                consume()
                return {'type': 'NOT', 'children': [parse_not()]}
            return parse_primary()

        def parse_primary():
            t = peek()
            if t is None:
                raise ValueError("Unexpected end of query")
            if t == '(':
                consume()
                node = parse_or()
                if peek() != ')':
                    raise ValueError("Missing closing ')'")
                consume()
                return node
            if t.upper() in ('AND', 'OR', 'NOT') or t in (')', '~'):
                raise ValueError(f"Unexpected token: {t}")
            consume()
            name = t.upper()
            if name not in self.named_conditions:
                raise ValueError(f"Unknown saved condition: '{name}' — create it first via 'Manage Named Conditions...'")
            return {'type': 'REF', 'name': name}

        result = parse_or()
        if pos[0] != len(tokens):
            raise ValueError(f"Unexpected extra token: {tokens[pos[0]]}")
        return result

    # ------------------------------------------------------------------
    # NAMED CONDITIONS MANAGER
    # ------------------------------------------------------------------

    def open_named_conditions_manager(self, preselect=None):
        win = tk.Toplevel(self.root)
        win.title("Manage Named Conditions")
        win.geometry("760x600")

        left = ttk.Frame(win, width=220)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        ttk.Label(left, text="Saved Conditions", font=('Arial', 11, 'bold')).pack(pady=4)
        listbox = tk.Listbox(left, height=24)
        listbox.pack(fill=tk.BOTH, expand=True, pady=4)

        right = ttk.Frame(win)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        name_label = ttk.Label(right, text="No saved condition selected", font=('Arial', 12, 'bold'))
        name_label.pack(anchor=tk.W, pady=(0, 6))

        ctx = TreeContext(
            tree_widget=None,
            get_root=lambda: self.named_conditions.get(self.active_named_name),
            set_root=lambda n: self.named_conditions.__setitem__(self.active_named_name, n),
        )
        ctx.tree_widget = self.build_condition_tab(right, ctx)

        def refresh_list(select_name=None):
            listbox.delete(0, tk.END)
            names = sorted(self.named_conditions.keys())
            for n in names:
                listbox.insert(tk.END, n)
            if select_name and select_name in names:
                listbox.selection_set(names.index(select_name))
                on_select(None)

        def on_select(event):
            sel = listbox.curselection()
            if not sel:
                return
            names = sorted(self.named_conditions.keys())
            self.active_named_name = names[sel[0]]
            name_label.config(text=self.active_named_name)
            self.refresh_condition_tree(ctx)

        listbox.bind('<<ListboxSelect>>', on_select)

        def add_new():
            name = simpledialog.askstring("New Saved Condition", "Name (letters/numbers/underscore only):", parent=win)
            if not name:
                return
            name = name.strip().upper()
            if not re.match(r'^[A-Z_][A-Z0-9_]*$', name):
                messagebox.showerror("Invalid name", "Use only letters, numbers, underscore — must not start with a digit")
                return
            if name in ('AND', 'OR', 'NOT'):
                messagebox.showerror("Reserved word", f"'{name}' is a reserved query keyword")
                return
            if name in self.named_conditions:
                messagebox.showerror("Already exists", f"'{name}' already exists")
                return
            self.named_conditions[name] = None
            refresh_list(select_name=name)

        def rename_selected():
            sel = listbox.curselection()
            if not sel:
                return
            old_name = sorted(self.named_conditions.keys())[sel[0]]
            new_name = simpledialog.askstring("Rename", "New name:", initialvalue=old_name, parent=win)
            if not new_name:
                return
            new_name = new_name.strip().upper()
            if new_name == old_name:
                return
            if new_name in self.named_conditions:
                messagebox.showerror("Already exists", f"'{new_name}' already exists")
                return
            self.named_conditions[new_name] = self.named_conditions.pop(old_name)
            self._rename_refs_everywhere(old_name, new_name)
            if self.active_named_name == old_name:
                self.active_named_name = new_name
            refresh_list(select_name=new_name)

        def delete_selected():
            sel = listbox.curselection()
            if not sel:
                return
            name = sorted(self.named_conditions.keys())[sel[0]]
            if not messagebox.askyesno("Confirm Delete", f"Delete saved condition '{name}'? "
                                                           f"Anything still referencing it will fail to compile until fixed."):
                return
            del self.named_conditions[name]
            if self.active_named_name == name:
                self.active_named_name = None
                name_label.config(text="No saved condition selected")
                ctx.tree_widget.delete(*ctx.tree_widget.get_children())
            refresh_list()

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X, pady=4)
        ttk.Button(btns, text="New", command=add_new).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Rename", command=rename_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Delete", command=delete_selected).pack(side=tk.LEFT, padx=2)

        refresh_list(select_name=preselect)

    def _rename_refs_everywhere(self, old_name, new_name):
        def walk(node):
            if node is None:
                return
            if node['type'] == 'REF' and node['name'] == old_name:
                node['name'] = new_name
            elif node['type'] in ('AND', 'OR', 'NOT'):
                for c in node['children']:
                    walk(c)
        for n in self.named_conditions.values():
            walk(n)
        for d in self.decisions.values():
            walk(d['visibility'])
            walk(d['availability'])

    # ------------------------------------------------------------------
    # EFFECTS LIST EDITING
    # ------------------------------------------------------------------

    def refresh_effects_list(self):
        self.effects_listbox.delete(0, tk.END)
        if self.active_id is None:
            return
        for eff in self.decisions[self.active_id]['effects']:
            self.effects_listbox.insert(tk.END, self.describe_effect(eff))

    def add_effect(self):
        if self.active_id is None:
            messagebox.showwarning("No decision selected", "Select a decision first")
            return
        if not self.countries:
            messagebox.showwarning("Load countries first", "Load countries.c before adding effects")
            return
        dialog = EffectDialog(self.root, self.countries, self.provinces, self.leaders)
        if dialog.result_data is None:
            return
        self.decisions[self.active_id]['effects'].append(dialog.result_data)
        self.refresh_effects_list()
        self.refresh_decision_list()

    def edit_effect(self):
        sel = self.effects_listbox.curselection()
        if not sel:
            return
        eff = self.decisions[self.active_id]['effects'][sel[0]]
        dialog = EffectDialog(self.root, self.countries, self.provinces, self.leaders, initial=eff)
        if dialog.result_data is None:
            return
        self.decisions[self.active_id]['effects'][sel[0]] = dialog.result_data
        self.refresh_effects_list()

    def delete_effect(self):
        sel = self.effects_listbox.curselection()
        if not sel:
            return
        del self.decisions[self.active_id]['effects'][sel[0]]
        self.refresh_effects_list()
        self.refresh_decision_list()

    def move_effect(self, direction):
        sel = self.effects_listbox.curselection()
        if not sel:
            return
        i = sel[0]; j = i + direction
        effects = self.decisions[self.active_id]['effects']
        if j < 0 or j >= len(effects):
            return
        effects[i], effects[j] = effects[j], effects[i]
        self.refresh_effects_list()
        self.effects_listbox.selection_set(j)

    # ------------------------------------------------------------------
    # SAVE / LOAD PROJECT
    # ------------------------------------------------------------------

    def save_project(self):
        self.commit_form_to_active()
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not filename:
            return
        data = {
            'decisions': {str(k): v for k, v in self.decisions.items()},
            'next_decision_id': self.next_decision_id,
            'named_conditions': self.named_conditions,
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
            self.decisions = {int(k): self.ensure_decision_defaults(v) for k, v in data['decisions'].items()}
            self.next_decision_id = data.get('next_decision_id', 0)
            self.named_conditions = data.get('named_conditions', {})
            self.active_id = None
            self.form_title.config(text="No decision selected")
            self.refresh_decision_list()
            messagebox.showinfo("Success", "Project loaded")
        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def validate_tree(self, node, path, errors):
        if node is None or node['type'] in ('LEAF', 'REF'):
            return
        if node['type'] == 'NOT' and len(node['children']) != 1:
            errors.append(f"{path}: NOT group must have exactly 1 child (has {len(node['children'])})")
        if node['type'] in ('AND', 'OR') and len(node['children']) < 1:
            errors.append(f"{path}: {node['type']} group has no children")
        for child in node['children']:
            self.validate_tree(child, path, errors)

    def check_named_condition_cycles(self):
        errors = []
        def visit(name, stack):
            if name in stack:
                errors.append(f"Cycle in named conditions: {' -> '.join(stack + [name])}")
                return
            if name not in self.named_conditions:
                errors.append(f"Named condition '{name}' referenced but not defined")
                return
            stack = stack + [name]
            def walk(node):
                if node is None:
                    return
                if node['type'] == 'REF':
                    visit(node['name'], stack)
                elif node['type'] in ('AND', 'OR', 'NOT'):
                    for c in node['children']:
                        walk(c)
            walk(self.named_conditions[name])
        for name in self.named_conditions:
            visit(name, [])
        return errors

    # ------------------------------------------------------------------
    # COMPILE / EXPORT
    # ------------------------------------------------------------------

    def escape_c_string(self, s):
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    def leaf_operands(self, node):
        ctype = node['condition']; p = node['params']
        if ctype == 'COUNTRY_IS': return p.get('country_id', 0), 0
        if ctype in ('STABILITY_GE', 'STABILITY_LE'): return p.get('value', 0), 0
        if ctype in ('SUPPORT_GE', 'SUPPORT_LE'): return p.get('ideology', 0), p.get('value', 0)
        if ctype == 'RULING_IS': return p.get('ideology', 0), 0
        if ctype == 'CONTROLS_PROVINCE': return p.get('province_id', 0), 0
        if ctype == 'DECISION_TAKEN': return p.get('decision_id', -1), 0
        return 0, 0

    def compile_condition_tree(self, node, expanding=None):
        if expanding is None:
            expanding = set()
        instrs = []
        def visit(n):
            if n is None:
                return
            if n['type'] == 'LEAF':
                op1, op2 = self.leaf_operands(n)
                instrs.append((n['condition'], op1, op2))
            elif n['type'] == 'REF':
                name = n['name']
                if name in expanding:
                    raise ValueError(f"Cycle detected expanding saved condition '{name}'")
                if name not in self.named_conditions:
                    raise ValueError(f"Saved condition '{name}' not found")
                expanding.add(name)
                instrs.extend(self.compile_condition_tree(self.named_conditions[name], expanding))
                expanding.discard(name)
            elif n['type'] == 'NOT':
                visit(n['children'][0])
                instrs.append(('NOT', 0, 0))
            else:
                children = n['children']
                visit(children[0])
                for child in children[1:]:
                    visit(child)
                    instrs.append((n['type'], 0, 0))
        visit(node)
        return instrs

    def effect_operands(self, eff):
        etype = eff['effect']; p = eff['params']
        if etype == 'ADD_STABILITY': return p.get('delta', 0), 0
        if etype == 'ADD_SUPPORT': return p.get('ideology', 0), p.get('delta', 0)
        if etype == 'SET_RULING_IDEOLOGY': return p.get('ideology', 0), 0
        if etype == 'SET_PROVINCE_OWNER': return p.get('province_id', 0), p.get('country_id', EFFECT_COUNTRY_SELF)
        if etype == 'SET_LEADER': return p.get('leader', -1), 0
        if etype == 'CLEAR_LEADER': return p.get('country_id', EFFECT_COUNTRY_SELF), p.get('ideology', 0)
        if etype == 'FORM_NATION': return p.get('formed_country', 0), 0
        if etype == 'ABSORB_COUNTRY': return p.get('absorbed_country', 0), p.get('into_country', EFFECT_COUNTRY_SELF)
        if etype == 'ADD_CORE': return p.get('province_id', 0), p.get('country_id', EFFECT_COUNTRY_SELF)
        return 0, 0

    def export_to_c(self):
        self.commit_form_to_active()
        if not self.decisions:
            messagebox.showwarning("Nothing to export", "Add at least one decision first")
            return

        errors = self.check_named_condition_cycles()
        for did, d in self.decisions.items():
            self.validate_tree(d['visibility'], f"'{d['title']}' visibility", errors)
            self.validate_tree(d['availability'], f"'{d['title']}' availability", errors)

        if errors:
            messagebox.showerror("Invalid data", "Fix these before exporting:\n\n" +
                                  "\n".join(errors[:15]) + ("\n..." if len(errors) > 15 else ""))
            return

        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return

        try:
            condition_pool = []
            effect_pool = []
            decision_rows = []

            for did in sorted(self.decisions.keys()):
                d = self.decisions[did]

                if d['visibility'] is None:
                    vis_off, vis_len = 0, 0xFFFF
                else:
                    instrs = self.compile_condition_tree(d['visibility'])
                    vis_off, vis_len = len(condition_pool), len(instrs)
                    condition_pool.extend(instrs)

                if d['availability'] is None:
                    avail_off, avail_len = 0, 0xFFFF
                else:
                    instrs = self.compile_condition_tree(d['availability'])
                    avail_off, avail_len = len(condition_pool), len(instrs)
                    condition_pool.extend(instrs)

                fx_off = len(effect_pool)
                for eff in d['effects']:
                    op1, op2 = self.effect_operands(eff)
                    effect_pool.append((eff['effect'], op1, op2))
                fx_len = len(d['effects'])

                cooldown = DECISION_ONCE_ONLY if d['once_only'] else d['cooldown_turns']

                decision_rows.append((d['title'], d['flavor_text'], d['effect_text'], d['prerequisites_text'],
                                       cooldown, vis_off, vis_len, avail_off, avail_len, fx_off, fx_len))

            with open(f"{output_dir}/decisions_data.h", 'w', encoding='utf-8') as f:
                f.write("#ifndef DECISIONS_DATA_H\n#define DECISIONS_DATA_H\n\n")

                f.write("// Keep in sync with CONDOP_ORDER in decision_editor.py\n")
                f.write("typedef enum {\n")
                for i, name in enumerate(CONDOP_ORDER):
                    f.write(f"    CONDOP_{name} = {i},\n")
                f.write("} ConditionOp;\n\n")

                f.write("// Postfix (RPN) instruction. AND/OR: pop 2 push 1 ; NOT: pop 1 push 1 ;\n")
                f.write("// all others: push 1, a leaf evaluated against the country being checked.\n")
                f.write("//   COUNTRY_IS: op1=country_id\n")
                f.write("//   STABILITY_GE/LE: op1=value(0-100)\n")
                f.write("//   SUPPORT_GE/LE: op1=ideology, op2=value(0-100)\n")
                f.write("//   RULING_IS: op1=ideology\n")
                f.write("//   CONTROLS_PROVINCE: op1=province_id\n")
                f.write("//   DECISION_TAKEN: op1=decision index into decisions[] — requires a runtime\n")
                f.write("//     `bool decision_taken[DECISION_COUNT]` global (any country, ever), not built yet\n")
                f.write("typedef struct { unsigned char opcode; short operand1; short operand2; } ConditionInstr;\n\n")
                f.write("#define CONDITION_ALWAYS_TRUE 0xFFFF // sentinel length: no tree, always true\n\n")

                f.write("// Keep in sync with EFFECTOP_ORDER in decision_editor.py\n")
                f.write("typedef enum {\n")
                for i, name in enumerate(EFFECTOP_ORDER):
                    f.write(f"    EFFECTOP_{name} = {i},\n")
                f.write("} EffectOp;\n\n")

                f.write("#define EFFECT_COUNTRY_SELF -1 // sentinel: acting country\n\n")

                f.write("//   ADD_STABILITY: op1=delta (signed, acting country)\n")
                f.write("//   ADD_SUPPORT: op1=ideology, op2=delta (signed, acting country)\n")
                f.write("//   SET_RULING_IDEOLOGY: op1=ideology (acting country)\n")
                f.write("//   SET_PROVINCE_OWNER: op1=province_id, op2=country_id or EFFECT_COUNTRY_SELF\n")
                f.write("//   SET_LEADER: op1=leader PORTRAIT_ID (stable id, NOT array index) — game code\n")
                f.write("//     must linear-search leaders[] for a matching portrait_id at apply-time to find\n")
                f.write("//     that leader's country_id/ideology/current array index\n")
                f.write("//   CLEAR_LEADER: op1=country_id or EFFECT_COUNTRY_SELF, op2=ideology\n")
                f.write("//   FORM_NATION: op1=formed_country_id — acting country transforms into it:\n")
                f.write("//     transfers acting country's provinces, copies its political state over,\n")
                f.write("//     deactivates old identity (unless same id), PLAYER_COUNTRY follows if applicable\n")
                f.write("//   ABSORB_COUNTRY: op1=absorbed_country_id, op2=into country_id or EFFECT_COUNTRY_SELF\n")
                f.write("//   ADD_CORE: op1=province_id, op2=country_id or EFFECT_COUNTRY_SELF — appends to a\n")
                f.write("//     bounded runtime core list (MAX_RUNTIME_CORES in decisions.cpp), NOT province_cores.c\n")
                f.write("typedef struct { unsigned char opcode; short operand1; short operand2; } EffectInstr;\n\n")

                f.write("typedef struct {\n")
                f.write("    const char* title;\n")
                f.write("    const char* flavor_text;         // may contain literal \\n — split before rendering\n")
                f.write("    const char* effect_text;          // human-authored, not auto-generated\n")
                f.write("    const char* prerequisites_text;   // auto-generated from availability, editable — SHOW to player\n")
                f.write("    short cooldown_turns;              // DECISION_ONCE_ONLY(-1) = never repeatable; else turns before retakeable\n")
                f.write("    unsigned short visibility_offset;\n")
                f.write("    unsigned short visibility_length;   // CONDITION_ALWAYS_TRUE = always visible\n")
                f.write("    unsigned short availability_offset;\n")
                f.write("    unsigned short availability_length; // CONDITION_ALWAYS_TRUE = always available\n")
                f.write("    unsigned short effects_offset;\n")
                f.write("    unsigned short effects_length;\n")
                f.write("} Decision;\n\n")

                f.write("#define DECISION_ONCE_ONLY -1\n\n")
                f.write(f"#define CONDITION_POOL_COUNT {len(condition_pool)}\n")
                f.write("extern const ConditionInstr condition_pool[CONDITION_POOL_COUNT];\n\n")
                f.write(f"#define EFFECT_POOL_COUNT {len(effect_pool)}\n")
                f.write("extern const EffectInstr effect_pool[EFFECT_POOL_COUNT];\n\n")
                f.write(f"#define DECISION_COUNT {len(decision_rows)}\n")
                f.write("extern const Decision decisions[DECISION_COUNT];\n\n")
                f.write("#endif\n")

            with open(f"{output_dir}/decisions_data.c", 'w', encoding='utf-8') as f:
                f.write('#include "decisions_data.h"\n\n')

                f.write("const ConditionInstr condition_pool[CONDITION_POOL_COUNT] = {\n")
                for name, op1, op2 in condition_pool:
                    f.write(f"    {{ CONDOP_{name}, {op1}, {op2} }},\n")
                f.write("};\n\n")

                f.write("const EffectInstr effect_pool[EFFECT_POOL_COUNT] = {\n")
                for name, op1, op2 in effect_pool:
                    f.write(f"    {{ EFFECTOP_{name}, {op1}, {op2} }},\n")
                f.write("};\n\n")

                f.write("const Decision decisions[DECISION_COUNT] = {\n")
                for row in decision_rows:
                    title, flavor, efftext, prereq, cooldown, vo, vl, ao, al, fo, fl = row
                    f.write(f'    {{ "{self.escape_c_string(title)}", "{self.escape_c_string(flavor)}", '
                            f'"{self.escape_c_string(efftext)}", "{self.escape_c_string(prereq)}", '
                            f'{cooldown}, {vo}, {vl}, {ao}, {al}, {fo}, {fl} }},\n')
                f.write("};\n")

            messagebox.showinfo("Export Complete",
                                 f"Exported to {output_dir}\n\n"
                                 f"- decisions_data.h/c ({len(decision_rows)} decisions, "
                                 f"{len(condition_pool)} condition instrs, {len(effect_pool)} effect instrs)")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            import traceback
            traceback.print_exc()


# ----------------------------------------------------------------------
# LEAF CONDITION DIALOG
# ----------------------------------------------------------------------

class LeafConditionDialog(simpledialog.Dialog):
    def __init__(self, parent, countries, provinces, decisions, current_decision_id, initial=None):
        self.countries = countries
        self.provinces = provinces
        self.decisions = decisions
        self.current_decision_id = current_decision_id
        self.initial = initial or {}
        self.result_data = None
        self.param_widgets = {}
        super().__init__(parent, title="Condition")

    def body(self, master):
        ttk.Label(master, text="Condition type:").grid(row=0, column=0, sticky='w')
        self.type_var = tk.StringVar(value=self.initial.get('condition', list(CONDITION_TYPES.keys())[0]))
        combo = ttk.Combobox(master, textvariable=self.type_var, values=list(CONDITION_TYPES.keys()), state='readonly', width=22)
        combo.grid(row=0, column=1, sticky='we', pady=(0, 8))
        combo.bind('<<ComboboxSelected>>', lambda e: self.rebuild_params())

        self.param_frame = ttk.Frame(master)
        self.param_frame.grid(row=1, column=0, columnspan=3, sticky='we')
        self.rebuild_params()
        return combo

    def rebuild_params(self):
        for w in self.param_frame.winfo_children():
            w.destroy()
        self.param_widgets = {}

        ctype = self.type_var.get()
        schema = CONDITION_TYPES[ctype]['params']
        existing = self.initial.get('params', {}) if self.initial.get('condition') == ctype else {}

        for row, (pname, pkind) in enumerate(schema):
            ttk.Label(self.param_frame, text=pname + ":").grid(row=row, column=0, sticky='w', pady=2)

            if pkind == 'country':
                names = [c['name'] for c in self.countries]
                combo = ttk.Combobox(self.param_frame, values=names, state='readonly', width=24)
                idx = existing.get(pname, 0)
                combo.current(idx if 0 <= idx < len(names) else 0)
                combo.grid(row=row, column=1, sticky='we')
                self.param_widgets[pname] = ('country', combo)

            elif pkind == 'ideology':
                combo = ttk.Combobox(self.param_frame, values=IDEOLOGIES, state='readonly', width=24)
                idx = existing.get(pname, 0)
                combo.current(idx if 0 <= idx < 4 else 0)
                combo.grid(row=row, column=1, sticky='we')
                self.param_widgets[pname] = ('ideology', combo)

            elif pkind == 'percent':
                var = tk.IntVar(value=existing.get(pname, 50))
                ttk.Spinbox(self.param_frame, from_=0, to=100, textvariable=var, width=6).grid(row=row, column=1, sticky='w')
                self.param_widgets[pname] = ('int', var)

            elif pkind == 'province':
                var = tk.IntVar(value=existing.get(pname, 0))
                ttk.Spinbox(self.param_frame, from_=0, to=774, textvariable=var, width=6).grid(row=row, column=1, sticky='w')
                name_label = ttk.Label(self.param_frame, text='')
                name_label.grid(row=row, column=2, sticky='w', padx=6)
                def refresh_label(*_a, v=var, lbl=name_label):
                    lbl.config(text=self.provinces.get(v.get(), '(no name — load province_data.c)'))
                var.trace_add('write', refresh_label); refresh_label()
                self.param_widgets[pname] = ('int', var)

            elif pkind == 'decision':
                ids_sorted = sorted(self.decisions.keys())
                labels = []
                for did in ids_sorted:
                    title = self.decisions[did]['title']
                    labels.append(f"{title} (this decision)" if did == self.current_decision_id else title)
                combo = ttk.Combobox(self.param_frame, values=labels, state='readonly', width=30)
                existing_did = existing.get(pname, ids_sorted[0] if ids_sorted else -1)
                idx = ids_sorted.index(existing_did) if existing_did in ids_sorted else 0
                if labels:
                    combo.current(idx)
                combo.grid(row=row, column=1, sticky='we')
                self.param_widgets[pname] = ('decision', (combo, ids_sorted))

    def validate(self):
        ctype = self.type_var.get()
        for pname, pkind in CONDITION_TYPES[ctype]['params']:
            if pkind == 'decision':
                _, (combo, ids_sorted) = self.param_widgets[pname]
                if not ids_sorted:
                    messagebox.showerror("No decisions", "No decisions exist yet to reference")
                    return False
        return True

    def apply(self):
        ctype = self.type_var.get()
        params = {}
        for pname, pkind in CONDITION_TYPES[ctype]['params']:
            kind, widget = self.param_widgets[pname]
            if kind in ('country', 'ideology'):
                params[pname] = widget.current()
            elif kind == 'decision':
                combo, ids_sorted = widget
                params[pname] = ids_sorted[combo.current()]
            else:
                params[pname] = widget.get()
        self.result_data = {'type': 'LEAF', 'condition': ctype, 'params': params}


# ----------------------------------------------------------------------
# EFFECT DIALOG
# ----------------------------------------------------------------------

class EffectDialog(simpledialog.Dialog):
    def __init__(self, parent, countries, provinces, leaders, initial=None):
        self.countries = countries
        self.provinces = provinces
        self.leaders = leaders
        self.initial = initial or {}
        self.result_data = None
        self.param_widgets = {}
        super().__init__(parent, title="Effect")

    def _leader_label(self, l):
        cname = next((c['name'] for c in self.countries if c['id'] == l['country_id']), '?')
        return f"{l['name']} ({cname}, {IDEOLOGIES[l['ideology']]})"

    def body(self, master):
        ttk.Label(master, text="Effect type:").grid(row=0, column=0, sticky='w')
        self.type_var = tk.StringVar(value=self.initial.get('effect', list(EFFECT_TYPES.keys())[0]))
        combo = ttk.Combobox(master, textvariable=self.type_var, values=list(EFFECT_TYPES.keys()), state='readonly', width=26)
        combo.grid(row=0, column=1, sticky='we', pady=(0, 8))
        combo.bind('<<ComboboxSelected>>', lambda e: self.rebuild_params())

        self.param_frame = ttk.Frame(master)
        self.param_frame.grid(row=1, column=0, columnspan=3, sticky='we')
        self.rebuild_params()
        return combo

    def rebuild_params(self):
        for w in self.param_frame.winfo_children():
            w.destroy()
        self.param_widgets = {}

        etype = self.type_var.get()
        schema = EFFECT_TYPES[etype]['params']
        existing = self.initial.get('params', {}) if self.initial.get('effect') == etype else {}

        for row, (pname, pkind) in enumerate(schema):
            ttk.Label(self.param_frame, text=pname + ":").grid(row=row, column=0, sticky='w', pady=2)

            if pkind == 'ideology':
                combo = ttk.Combobox(self.param_frame, values=IDEOLOGIES, state='readonly', width=24)
                idx = existing.get(pname, 0)
                combo.current(idx if 0 <= idx < 4 else 0)
                combo.grid(row=row, column=1, sticky='we')
                self.param_widgets[pname] = ('ideology', combo)

            elif pkind == 'delta_percent':
                var = tk.IntVar(value=existing.get(pname, 0))
                ttk.Spinbox(self.param_frame, from_=-100, to=100, textvariable=var, width=6).grid(row=row, column=1, sticky='w')
                self.param_widgets[pname] = ('int', var)

            elif pkind == 'province':
                var = tk.IntVar(value=existing.get(pname, 0))
                ttk.Spinbox(self.param_frame, from_=0, to=774, textvariable=var, width=6).grid(row=row, column=1, sticky='w')
                name_label = ttk.Label(self.param_frame, text='')
                name_label.grid(row=row, column=2, sticky='w', padx=6)
                def refresh_label(*_a, v=var, lbl=name_label):
                    lbl.config(text=self.provinces.get(v.get(), '(no name — load province_data.c)'))
                var.trace_add('write', refresh_label); refresh_label()
                self.param_widgets[pname] = ('int', var)

            elif pkind == 'country':
                names = [c['name'] for c in self.countries]
                combo = ttk.Combobox(self.param_frame, values=names, state='readonly', width=24)
                idx = existing.get(pname, 0)
                combo.current(idx if 0 <= idx < len(names) else 0)
                combo.grid(row=row, column=1, sticky='we')
                self.param_widgets[pname] = ('country', combo)

            elif pkind == 'country_or_self':
                names = ["SELF (acting country)"] + [c['name'] for c in self.countries]
                combo = ttk.Combobox(self.param_frame, values=names, state='readonly', width=24)
                existing_cid = existing.get(pname, EFFECT_COUNTRY_SELF)
                combo.current(0 if existing_cid == EFFECT_COUNTRY_SELF else existing_cid + 1)
                combo.grid(row=row, column=1, sticky='we')
                self.param_widgets[pname] = ('country_or_self', combo)

            elif pkind == 'leader':
                labels = [self._leader_label(l) for l in self.leaders]
                combo = ttk.Combobox(self.param_frame, values=labels, state='readonly', width=30)
                existing_lid = existing.get(pname, self.leaders[0]['portrait_id'] if self.leaders else -1)
                idx = next((i for i, l in enumerate(self.leaders) if l['portrait_id'] == existing_lid), 0)
                if labels:
                    combo.current(idx)
                combo.grid(row=row, column=1, sticky='we')
                self.param_widgets[pname] = ('leader', combo)

    def validate(self):
        etype = self.type_var.get()
        for pname, pkind in EFFECT_TYPES[etype]['params']:
            if pkind == 'leader' and not self.leaders:
                messagebox.showerror("No leaders loaded", "Load political_data.c first to reference a leader")
                return False
        return True

    def apply(self):
        etype = self.type_var.get()
        params = {}
        for pname, pkind in EFFECT_TYPES[etype]['params']:
            kind, widget = self.param_widgets[pname]
            if kind in ('ideology', 'country'):
                params[pname] = widget.current()
            elif kind == 'country_or_self':
                idx = widget.current()
                params[pname] = EFFECT_COUNTRY_SELF if idx == 0 else idx - 1
            elif kind == 'leader':
                idx = widget.current()
                params[pname] = self.leaders[idx]['portrait_id'] if self.leaders else -1
            else:
                params[pname] = widget.get()
        self.result_data = {'effect': etype, 'params': params}


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1080x840")
    app = DecisionEditor(root)
    root.mainloop()