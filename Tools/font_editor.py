"""
Font Editor — author tool for Pocket Wars

Hand-design an 8-row bitmap font, glyph by glyph, with a per-glyph ADVANCE
WIDTH (1-8px) for non-monospaced rendering. No AI-generated glyph data —
every pixel is placed by hand in this tool.

IMPORTANT LIMITATION, know this before you invest time tuning widths:
Only the MAIN-engine (menu/popup) sprite-based text renderer can actually
use variable widths — each sprite is positioned individually, so its
advance can vary per glyph. The SUB-engine (province info panel) renders
through a BG tile layer, which is grid-locked to one glyph per fixed 8px
cell — that's a hardware/tilemap constraint, not something font data can
work around. Widths you set here will visibly change main-engine text;
the info panel will stay monospaced regardless of what's authored here.

Can load your EXISTING font_data.h (the 8x8-bitmap-only format, no widths)
and infers a starting width per glyph from each bitmap's actual ink (tight
bounding box + a little spacing) — so importing your current ~150 glyphs
gives you a working starting point to hand-tune, not a blank font.

Exports font_data.h with an added `width` field on the Glyph struct:

    struct Glyph {
        char16_t c;
        u8 rows[8];  // 8x8 bitmap, 1 bit per pixel, bit7 = leftmost column
        u8 width;    // advance width in px (1-8). Main-engine sprite text
                      // only — sub-engine BG-tile text ignores this and
                      // always advances by the fixed CHAR_W grid cell.
    };

CHAR_W/CHAR_H (8/8) are UNCHANGED in meaning — they're still the fixed
bitmap canvas size / BG-tile grid cell size the sub-engine relies on.
The new `width` field is a separate, additional per-glyph value.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import re

ROWS = 8
COLS = 8
CELL_PX = 30                 # edit canvas: pixels per bitmap cell
PREVIEW_SCALE = 4            # preview strip: pixels per bitmap cell

DEFAULT_BLANK_WIDTH = 4       # advance for a newly-created empty glyph (e.g. space)


class FontEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Font Editor")

        # char (python str, len 1) -> {'rows': [8 x int 0-255], 'width': int 1-8}
        self.glyphs = {}
        self.active_char = None
        self._paint_val = 1   # while dragging on the edit canvas, value being painted

        self.setup_gui()

    # ------------------------------------------------------------------
    # font_data.h PARSER (import existing glyphs, no width field present yet)
    # ------------------------------------------------------------------

    def parse_font_data_h(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Matches: { u'X', { 0xNN, 0xNN, ..., 0xNN } },   (8 hex bytes)
        # Char literal group handles the one escaped case in this dataset (u'\'')
        # and otherwise expects a single literal UTF-8 character between the quotes.
        pattern = re.compile(
            r"\{\s*u'((?:\\.|[^'\\])+)'\s*,\s*\{\s*((?:0x[0-9A-Fa-f]{2}\s*,?\s*){8})\}\s*\}"
        )

        glyphs = {}
        for char_lit, rows_blob in pattern.findall(content):
            if char_lit == "\\'":
                ch = "'"
            elif char_lit == "\\\\":
                ch = "\\"
            elif len(char_lit) == 1:
                ch = char_lit
            else:
                continue  # unrecognized escape — skip rather than guess wrong

            rows = [int(h, 16) for h in re.findall(r'0x[0-9A-Fa-f]{2}', rows_blob)]
            if len(rows) != 8:
                continue

            glyphs[ch] = {'rows': rows, 'width': self.infer_width(rows, ch)}

        return glyphs

    def infer_width(self, rows, ch):
        """Tight-bbox + 1px spacing, with a sane fallback for blank glyphs (e.g. space)."""
        max_col = -1
        for byte in rows:
            for col in range(COLS):
                if byte & (0x80 >> col):
                    max_col = max(max_col, col)

        if max_col < 0:
            return DEFAULT_BLANK_WIDTH
        return min(COLS, max_col + 2)

    # ------------------------------------------------------------------
    # GUI SETUP
    # ------------------------------------------------------------------

    def setup_gui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        # ---- Left: glyph list + file ops ----
        left = ttk.Frame(main, width=260)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)

        ttk.Label(left, text="Glyphs", font=('Arial', 12, 'bold')).pack(pady=5)

        self.glyph_listbox = tk.Listbox(left, height=28, font=('Courier', 10))
        self.glyph_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.glyph_listbox.bind('<<ListboxSelect>>', self.on_glyph_select)

        add_row = ttk.Frame(left)
        add_row.pack(fill=tk.X, pady=(4, 2))
        self.new_char_var = tk.StringVar()
        ttk.Entry(add_row, textvariable=self.new_char_var, width=4).pack(side=tk.LEFT)
        ttk.Button(add_row, text="Add Glyph", command=self.add_glyph).pack(side=tk.LEFT, padx=4)
        ttk.Button(left, text="Duplicate Selected As...", command=self.duplicate_glyph).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Delete Selected Glyph", command=self.delete_glyph).pack(fill=tk.X, pady=2)

        ttk.Separator(left, orient='horizontal').pack(fill=tk.X, pady=8)

        ttk.Button(left, text="Import font_data.h", command=self.import_font_data).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Save Project",       command=self.save_project).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Load Project",       command=self.load_project).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Export font_data.h", command=self.export_font_data).pack(fill=tk.X, pady=2)

        self.status_label = ttk.Label(self.root, text="Import font_data.h or add a glyph to begin.", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # ---- Right: editor ----
        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.form_title = ttk.Label(right, text="No glyph selected", font=('Arial', 13, 'bold'))
        self.form_title.pack(anchor=tk.W, pady=(0, 8))

        edit_frame = ttk.LabelFrame(right, text="Pixel Grid (click, or click+drag to paint)", padding=8)
        edit_frame.pack(anchor=tk.W)

        self.edit_canvas = tk.Canvas(edit_frame, width=COLS * CELL_PX, height=ROWS * CELL_PX,
                                      bg='#222222', highlightthickness=1, highlightbackground='#888')
        self.edit_canvas.pack()
        self.edit_canvas.bind('<Button-1>', self.on_canvas_press)
        self.edit_canvas.bind('<B1-Motion>', self.on_canvas_drag)

        width_frame = ttk.Frame(right)
        width_frame.pack(anchor=tk.W, pady=8)
        ttk.Label(width_frame, text="Advance width (px):").pack(side=tk.LEFT)
        self.width_var = tk.IntVar(value=DEFAULT_BLANK_WIDTH)
        width_spin = ttk.Spinbox(width_frame, from_=1, to=COLS, width=4, textvariable=self.width_var,
                                  command=self.on_width_change)
        width_spin.pack(side=tk.LEFT, padx=6)
        width_spin.bind('<KeyRelease>', lambda e: self.on_width_change())
        ttk.Label(width_frame, text="(red line on the grid marks the advance point)").pack(side=tk.LEFT, padx=6)

        preview_frame = ttk.LabelFrame(right, text="Preview (renders with current widths, main-engine style)", padding=8)
        preview_frame.pack(fill=tk.X, pady=10)

        self.preview_var = tk.StringVar(value="The quick brown fox")
        preview_entry = ttk.Entry(preview_frame, textvariable=self.preview_var)
        preview_entry.pack(fill=tk.X, pady=(0, 6))
        preview_entry.bind('<KeyRelease>', lambda e: self.draw_preview())

        self.preview_canvas = tk.Canvas(preview_frame, width=560, height=ROWS * PREVIEW_SCALE + 8,
                                         bg='#222222', highlightthickness=1, highlightbackground='#888')
        self.preview_canvas.pack()

        ttk.Label(right,
                  text="Note: this preview approximates the main-engine sprite renderer (per-glyph advance).\n"
                       "The sub-engine info panel always renders monospaced at the fixed 8px grid regardless\n"
                       "of the widths set here — see the note at the top of the generated file.",
                  foreground="#555", justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 0))

    # ------------------------------------------------------------------
    # GLYPH LIST
    # ------------------------------------------------------------------

    def refresh_glyph_list(self):
        self.glyph_listbox.delete(0, tk.END)
        for ch in sorted(self.glyphs.keys(), key=lambda c: ord(c)):
            g = self.glyphs[ch]
            label = ch if ch != ' ' else '(space)'
            self.glyph_listbox.insert(tk.END, f"{label}   U+{ord(ch):04X}   w={g['width']}")

    def _char_from_listbox_index(self, idx):
        return sorted(self.glyphs.keys(), key=lambda c: ord(c))[idx]

    def on_glyph_select(self, event):
        sel = self.glyph_listbox.curselection()
        if not sel:
            return
        self.active_char = self._char_from_listbox_index(sel[0])
        self.load_editor_from_active()

    def add_glyph(self):
        text = self.new_char_var.get()
        if not text:
            messagebox.showwarning("No character", "Type a character in the box first")
            return

        ch = text[0]
        if ch in self.glyphs:
            messagebox.showwarning("Already exists", f"'{ch}' is already in the glyph set — select it from the list to edit it")
            return

        self.glyphs[ch] = {'rows': [0] * 8, 'width': DEFAULT_BLANK_WIDTH}
        self.new_char_var.set('')
        self.refresh_glyph_list()

        self.active_char = ch
        self.load_editor_from_active()
        self.status_label.config(text=f"Added '{ch}' — now {len(self.glyphs)} glyphs")

    def duplicate_glyph(self):
        sel = self.glyph_listbox.curselection()
        if not sel:
            messagebox.showwarning("No selection", "Select the glyph you want to copy FROM first")
            return

        source_ch = self._char_from_listbox_index(sel[0])
        source = self.glyphs[source_ch]

        text = simpledialog.askstring(
            "Duplicate Glyph",
            f"Copying '{source_ch}' (rows + width={source['width']}).\n\nNew character:"
        )
        if not text:
            return

        new_ch = text[0]
        if new_ch == source_ch:
            messagebox.showwarning("Same character", "That's the same character you're copying from")
            return

        if new_ch in self.glyphs:
            if not messagebox.askyesno("Already exists", f"'{new_ch}' already exists — overwrite it with a copy of '{source_ch}'?"):
                return

        self.glyphs[new_ch] = {'rows': list(source['rows']), 'width': source['width']}
        self.refresh_glyph_list()

        self.active_char = new_ch
        self.load_editor_from_active()
        self.status_label.config(text=f"'{new_ch}' created as a copy of '{source_ch}' — edit it to add the diacritic")

    def delete_glyph(self):
        sel = self.glyph_listbox.curselection()
        if not sel:
            messagebox.showwarning("No selection", "Select a glyph in the list first")
            return

        ch = self._char_from_listbox_index(sel[0])
        if not messagebox.askyesno("Confirm Delete", f"Delete glyph '{ch}'?"):
            return

        del self.glyphs[ch]
        self.active_char = None
        self.form_title.config(text="No glyph selected")
        self.edit_canvas.delete('all')
        self.refresh_glyph_list()

    # ------------------------------------------------------------------
    # EDITOR <-> DATA
    # ------------------------------------------------------------------

    def load_editor_from_active(self):
        if self.active_char is None:
            return

        g = self.glyphs[self.active_char]
        label = self.active_char if self.active_char != ' ' else '(space)'
        self.form_title.config(text=f"Editing: {label}  (U+{ord(self.active_char):04X})")
        self.width_var.set(g['width'])
        self.draw_edit_grid()
        self.draw_preview()

    def draw_edit_grid(self):
        self.edit_canvas.delete('all')
        if self.active_char is None:
            return

        g = self.glyphs[self.active_char]
        rows = g['rows']
        width = g['width']

        for row in range(ROWS):
            for col in range(COLS):
                on = bool(rows[row] & (0x80 >> col))
                x0, y0 = col * CELL_PX, row * CELL_PX
                x1, y1 = x0 + CELL_PX, y0 + CELL_PX
                fill = '#e8e8e8' if on else '#333333'
                self.edit_canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline='#555555')

        # Advance-width guide: red line after the last column included in the advance
        guide_x = width * CELL_PX
        self.edit_canvas.create_line(guide_x, 0, guide_x, ROWS * CELL_PX, fill='#ff4444', width=2)

    def _cell_from_event(self, event):
        col = event.x // CELL_PX
        row = event.y // CELL_PX
        if 0 <= col < COLS and 0 <= row < ROWS:
            return row, col
        return None

    def on_canvas_press(self, event):
        if self.active_char is None:
            return
        cell = self._cell_from_event(event)
        if not cell:
            return
        row, col = cell
        g = self.glyphs[self.active_char]
        currently_on = bool(g['rows'][row] & (0x80 >> col))
        self._paint_val = 0 if currently_on else 1
        self._set_pixel(row, col, self._paint_val)

    def on_canvas_drag(self, event):
        if self.active_char is None:
            return
        cell = self._cell_from_event(event)
        if not cell:
            return
        row, col = cell
        self._set_pixel(row, col, self._paint_val)

    def _set_pixel(self, row, col, val):
        g = self.glyphs[self.active_char]
        bit = 0x80 >> col
        if val:
            g['rows'][row] |= bit
        else:
            g['rows'][row] &= ~bit & 0xFF
        self.draw_edit_grid()
        self.draw_preview()

    def on_width_change(self):
        if self.active_char is None:
            return
        try:
            w = int(self.width_var.get())
        except (ValueError, tk.TclError):
            return
        w = max(1, min(COLS, w))
        self.glyphs[self.active_char]['width'] = w
        self.draw_edit_grid()
        self.draw_preview()
        self.refresh_glyph_list()

    # ------------------------------------------------------------------
    # PREVIEW
    # ------------------------------------------------------------------

    def draw_preview(self):
        self.preview_canvas.delete('all')
        text = self.preview_var.get()
        x = 4

        for ch in text:
            g = self.glyphs.get(ch)
            if g is None:
                # Missing glyph — draw a placeholder box so gaps are obvious, not silent
                self.preview_canvas.create_rectangle(x, 4, x + 4 * PREVIEW_SCALE, 4 + ROWS * PREVIEW_SCALE,
                                                      outline='#ff4444')
                x += 4 * PREVIEW_SCALE + PREVIEW_SCALE
                continue

            for row in range(ROWS):
                for col in range(COLS):
                    if g['rows'][row] & (0x80 >> col):
                        px = x + col * PREVIEW_SCALE
                        py = 4 + row * PREVIEW_SCALE
                        self.preview_canvas.create_rectangle(px, py, px + PREVIEW_SCALE, py + PREVIEW_SCALE,
                                                              fill='#e8e8e8', outline='')

            x += g['width'] * PREVIEW_SCALE

    # ------------------------------------------------------------------
    # IMPORT / SAVE / LOAD
    # ------------------------------------------------------------------

    def import_font_data(self):
        filepath = filedialog.askopenfilename(
            title="Select font_data.h",
            filetypes=[("Header files", "*.h"), ("All files", "*.*")]
        )
        if not filepath:
            return

        try:
            imported = self.parse_font_data_h(filepath)
            if not imported:
                messagebox.showwarning("Nothing found", "Couldn't find any glyph entries in that file")
                return

            overwrite = True
            if self.glyphs:
                overwrite = messagebox.askyesno(
                    "Existing glyphs",
                    f"You already have {len(self.glyphs)} glyphs loaded. Merge in {len(imported)} imported "
                    f"glyphs, overwriting any with the same character? (No = cancel import)"
                )
            if not overwrite:
                return

            self.glyphs.update(imported)
            self.active_char = None
            self.form_title.config(text="No glyph selected")
            self.edit_canvas.delete('all')
            self.refresh_glyph_list()
            self.status_label.config(text=f"Imported {len(imported)} glyphs — widths auto-inferred, tune as needed")
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")

    def save_project(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return

        data = {ch: g for ch, g in self.glyphs.items()}
        # JSON object keys must be strings — single-char keys round-trip fine as-is
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

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

            self.glyphs = data
            self.active_char = None
            self.form_title.config(text="No glyph selected")
            self.edit_canvas.delete('all')
            self.refresh_glyph_list()
            messagebox.showinfo("Success", "Project loaded")
        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def escape_char_literal(self, ch):
        if ch == "'":
            return "\\'"
        if ch == "\\":
            return "\\\\"
        return ch

    def export_font_data(self):
        if not self.glyphs:
            messagebox.showwarning("Nothing to export", "Add or import at least one glyph first")
            return

        zero_width = [ch for ch, g in self.glyphs.items() if g['width'] < 1]
        if zero_width:
            messagebox.showerror("Invalid widths", f"{len(zero_width)} glyph(s) have width < 1 — fix before exporting")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".h",
            initialfile="font_data.h",
            filetypes=[("Header files", "*.h"), ("All files", "*.*")]
        )
        if not filepath:
            return

        try:
            ordered = sorted(self.glyphs.keys(), key=lambda c: ord(c))

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("#ifndef FONT_DATA_H\n")
                f.write("#define FONT_DATA_H\n\n")
                f.write("#include <nds.h>\n\n")
                f.write("#define CHAR_W 8\n")
                f.write("#define CHAR_H 8\n\n")
                f.write("struct Glyph {\n")
                f.write("    char16_t c;\n")
                f.write("    u8 rows[8];  // 8x8 bitmap, 1 bit per pixel, bit7 = leftmost column\n")
                f.write("    u8 width;    // advance width in px (1-8). Main-engine sprite text only —\n")
                f.write("                 // sub-engine BG-tile text ignores this, always advances CHAR_W.\n")
                f.write("};\n\n")
                f.write("static const Glyph FONT_GLYPHS[] = {\n")

                for ch in ordered:
                    g = self.glyphs[ch]
                    lit = self.escape_char_literal(ch)
                    rows_str = ", ".join(f"0x{v:02X}" for v in g['rows'])
                    f.write(f"    {{ u'{lit}', {{ {rows_str} }}, {g['width']} }},\n")

                f.write("};\n\n")
                f.write("static const unsigned int FONT_GLYPH_COUNT = sizeof(FONT_GLYPHS) / sizeof(Glyph);\n\n")
                f.write("#endif // FONT_DATA_H\n")

            messagebox.showinfo("Export Complete", f"Exported {len(ordered)} glyphs to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("900x760")
    app = FontEditor(root)
    root.mainloop()