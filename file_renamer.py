import json
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

PATTERN = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})(.*)$")
# Store the config next to the running exe/script rather than the user's home dir,
# since a roaming/network home folder can make that path slow to reach.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / "file_renamer_config.json"


class RenamerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Batch File Renamer (MM-DD-YYYY to YYYY-MM-DD)")
        self.geometry("825x520")

        self.folder_path = tk.StringVar()
        self.matched_files = []  # List of tuples: (original_path, new_name)

        last_folder = self.load_last_folder()
        if last_folder:
            self.folder_path.set(last_folder)
            # Validate after the window is shown, so a slow/unreachable path
            # (network share, VPN drive, cloud-synced folder) can't freeze startup.
            self.after(100, self.validate_last_folder)

        # Top Section: Folder Selection
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Folder:").pack(side=tk.LEFT)
        self.path_entry = ttk.Entry(
            top_frame, textvariable=self.folder_path, width=50
        )
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        browse_btn = ttk.Button(
            top_frame, text="Browse...", command=self.browse_folder
        )
        browse_btn.pack(side=tk.LEFT)

        scan_btn = ttk.Button(
            top_frame, text="Scan folder for files", command=self.scan_folder
        )
        scan_btn.pack(side=tk.LEFT, padx=5)

        # Middle Section: Preview Table
        mid_frame = ttk.Frame(self, padding=10)
        mid_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Original Name", "New Name")
        self.tree = ttk.Treeview(
            mid_frame, columns=columns, show="headings", selectmode="none"
        )
        self.tree.heading("Original Name", text="Original Name")
        self.tree.heading("New Name", text="New Target Name")
        self.tree.column("Original Name", width=320)
        self.tree.column("New Name", width=320)
        self.tree.tag_configure("evenrow", background="#ffffff")
        self.tree.tag_configure("oddrow", background="#e8e8e8")

        scrollbar = ttk.Scrollbar(
            mid_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Section: Action Buttons and Status
        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(fill=tk.X)

        self.status_label = ttk.Label(
            bottom_frame, text="Select a folder to begin."
        )
        self.status_label.pack(side=tk.LEFT)

        self.rename_btn = ttk.Button(
            bottom_frame,
            text="Execute Rename",
            state=tk.DISABLED,
            command=self.execute_rename,
        )
        self.rename_btn.pack(side=tk.RIGHT)

    def browse_folder(self):
        selected = filedialog.askdirectory(
            initialdir=self.folder_path.get() or None
        )
        if selected:
            self.folder_path.set(selected)
            self.save_last_folder(selected)
            self.scan_folder()

    def load_last_folder(self):
        # Only reads the config file; does not touch the filesystem path itself,
        # since stat-ing an unreachable network/cloud path here could block startup.
        try:
            data = json.loads(CONFIG_PATH.read_text())
            folder = data.get("last_folder", "") if isinstance(data, dict) else ""
            return folder if isinstance(folder, str) else ""
        except (OSError, ValueError):
            return ""

    def validate_last_folder(self):
        if self.folder_path.get() and not Path(self.folder_path.get()).is_dir():
            self.folder_path.set("")
            self.status_label.config(
                text="Last folder is unavailable. Select a folder to begin."
            )

    def save_last_folder(self, folder):
        # Write to a temp file then rename, so a crash/concurrent write can't corrupt the config.
        tmp_path = CONFIG_PATH.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps({"last_folder": folder}))
            tmp_path.replace(CONFIG_PATH)
        except OSError:
            pass

    def scan_folder(self):
        raw_path = self.folder_path.get().strip().strip("\"'")
        if not raw_path:
            return

        folder = Path(raw_path)
        if not folder.is_dir():
            messagebox.showerror(
                "Error", f"Directory does not exist:\n{folder}"
            )
            return

        self.tree.delete(*self.tree.get_children())
        self.matched_files.clear()

        for item in folder.iterdir():
            if not item.is_file():
                continue
            match = PATTERN.match(item.name)
            if match:
                month, day, year, rest = match.groups()
                new_name = f"{year}-{int(month):02d}-{int(day):02d}{rest}"
                self.matched_files.append((item, new_name))
                row_tag = "evenrow" if len(self.matched_files) % 2 else "oddrow"
                self.tree.insert(
                    "", tk.END, values=(item.name, new_name), tags=(row_tag,)
                )

        count = len(self.matched_files)
        if count == 0:
            self.status_label.config(
                text="No files matching 'MM-DD-YYYY*' found."
            )
            self.rename_btn.config(state=tk.DISABLED)
        else:
            self.status_label.config(
                text=f"Found {count} file(s) ready to rename."
            )
            self.rename_btn.config(state=tk.NORMAL)

    def execute_rename(self):
        if not self.matched_files:
            return

        confirm = messagebox.askyesno(
            "Confirm Rename",
            f"Are you sure you want to rename {len(self.matched_files)} file(s)?",
        )
        if not confirm:
            return

        renamed_count = 0
        skipped_count = 0

        for original_path, new_name in self.matched_files:
            target_path = original_path.with_name(new_name)
            if target_path.exists():
                skipped_count += 1
                continue
            try:
                original_path.rename(target_path)
                renamed_count += 1
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to rename {original_path.name}:\n{e}"
                )
                break

        messagebox.showinfo(
            "Done",
            f"Successfully renamed: {renamed_count}\nSkipped (already exists): {skipped_count}",
        )
        self.scan_folder()


if __name__ == "__main__":
    app = RenamerApp()
    app.mainloop()