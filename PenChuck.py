import tkinter as tk
from tkinter import ttk
from tkinter import colorchooser, filedialog, messagebox
from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET


class PenChuckApp(tk.Tk):
    """Basic GUI framework for a rose engine pen chuck simulator."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Rose Engine Pen Chuck")
        self.geometry("1200x760")
        self.minsize(900, 560)
        self.rosette_dir = Path(r"C:\OctoPrint\basedir\5000\uploads\rosette")
        self.startup_status = "Ready"
        self.rosette_files: dict[str, Path] = {}
        self.pen_radius_max = 200.0
        self.default_zoom = 4.0
        self.pattern_line_width = 0.5
        self.pattern_line_color = "#0d5ea6"
        self.current_rosette_max_radius = 0.0
        self.simulation_running = False
        self.simulation_after_id: str | None = None
        self.simulation_points: list[tuple[float, float]] = []
        self.simulation_vectors: list[tuple[float, float]] = []
        self.simulation_index = 0
        self.pattern_tag: str | None = None
        self.pattern_run_counter: int = 0
        self.pen_marker_id: int | None = None
        self.drawn_patterns: list[tuple[str, list[tuple[float, float]]]] = []
        self.simulation_complete_callback = None
        self.script_running = False
        self.script_commands: list[str] = []
        self.script_command_index = 0
        self.script_repeat_total = 0
        self.script_repeat_index = 0

        self._build_layout()
        self._build_drawing_area()
        self._build_controls()
        self._build_scripting_pane()
        self._build_status_bar()

    def _build_layout(self) -> None:
        # Root grid: main content row + status row.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ttk.Frame(self, padding=10)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)
        self.main_frame.grid_columnconfigure(2, weight=0)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.status_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.status_frame.grid(row=1, column=0, sticky="ew")
        self.status_frame.grid_columnconfigure(0, weight=1)

    def _build_drawing_area(self) -> None:
        drawing_container = ttk.LabelFrame(self.main_frame, text="Drawing Area", padding=8)
        drawing_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        drawing_container.grid_columnconfigure(0, weight=1)
        drawing_container.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            drawing_container,
            background="#f5f5f5",
            highlightthickness=1,
            highlightbackground="#bbbbbb",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        zoom_row = ttk.Frame(drawing_container)
        zoom_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        zoom_row.grid_columnconfigure(1, weight=1)

        ttk.Label(zoom_row, text="Zoom").grid(row=0, column=0, sticky="w", padx=(2, 8))
        self.zoom_var = tk.DoubleVar(value=self.default_zoom)
        self.zoom_scale = ttk.Scale(
            zoom_row,
            from_=0.25,
            to=4.0,
            variable=self.zoom_var,
            command=self._on_zoom_changed,
        )
        self.zoom_scale.grid(row=0, column=1, sticky="ew")
        self.zoom_text = tk.StringVar(value="1.00x")
        ttk.Label(zoom_row, textvariable=self.zoom_text, width=7, anchor="e").grid(
            row=0, column=2, sticky="e", padx=(8, 0)
        )

        self._draw_placeholder_guides()

    def _build_controls(self) -> None:
        self.controls = ttk.LabelFrame(self.main_frame, text="Controls", padding=10)
        self.controls.grid(row=0, column=1, sticky="ns")

        self.controls.grid_columnconfigure(0, minsize=220)

        row = 0

        ttk.Label(self.controls, text="Simulation").grid(row=row, column=0, sticky="w")
        row += 1

        button_row = ttk.Frame(self.controls)
        button_row.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        button_row.grid_columnconfigure((0, 1), weight=1)
        self.start_button = ttk.Button(button_row, text="Start", command=self._start_simulation)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.stop_button = ttk.Button(button_row, text="Stop", command=self._stop_simulation)
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.stop_button.state(["disabled"])
        row += 1

        ttk.Separator(self.controls, orient="horizontal").grid(row=row, column=0, sticky="ew", pady=8)
        row += 1

        rosette_label_row = ttk.Frame(self.controls)
        rosette_label_row.grid(row=row, column=0, sticky="ew")
        rosette_label_row.grid_columnconfigure(0, weight=1)
        ttk.Label(rosette_label_row, text="Rosette").grid(row=0, column=0, sticky="w")
        ttk.Button(rosette_label_row, text="Refresh", width=7,
                   command=self._refresh_rosette_list).grid(row=0, column=1, sticky="e")
        row += 1
        rosette_values = self._load_rosette_names()
        default_rosette = rosette_values[0] if rosette_values else "No SVG files found"
        self.rosette_var = tk.StringVar(value=default_rosette)
        self.rosette_menu = ttk.Combobox(
            self.controls,
            textvariable=self.rosette_var,
            values=rosette_values,
            state="readonly",
        )
        self.rosette_menu.bind("<<ComboboxSelected>>", self._on_rosette_selected)
        self.rosette_menu.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        if not rosette_values:
            self.rosette_menu.state(["disabled"])
        row += 1

        ttk.Label(self.controls, text="Amplitude (mm)").grid(row=row, column=0, sticky="w")
        row += 1
        self.amplitude_str = tk.StringVar(value="0.00")
        ttk.Entry(self.controls, textvariable=self.amplitude_str, state="readonly", width=10).grid(
            row=row, column=0, sticky="ew", pady=(0, 10)
        )
        row += 1

        ttk.Label(self.controls, text="Pen Radius").grid(row=row, column=0, sticky="w")
        row += 1
        self.pen_radius = tk.DoubleVar(value=0.5)
        self.pen_radius_str = tk.StringVar(value=f"{self.pen_radius.get():.2f}")
        pen_radius_row = ttk.Frame(self.controls)
        pen_radius_row.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        pen_radius_row.grid_columnconfigure(0, weight=1)

        self.pen_radius_scale = ttk.Scale(
            pen_radius_row,
            from_=0.0,
            to=self.pen_radius_max,
            variable=self.pen_radius,
            command=self._on_pen_radius_slider,
        )
        self.pen_radius_scale.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        pen_radius_entry = ttk.Entry(pen_radius_row, textvariable=self.pen_radius_str, width=8)
        pen_radius_entry.grid(row=0, column=1, sticky="e")
        pen_radius_entry.bind("<Return>", self._on_pen_radius_entry)
        pen_radius_entry.bind("<FocusOut>", self._on_pen_radius_entry)
        row += 1

        pen_inc_row = ttk.Frame(self.controls)
        pen_inc_row.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        pen_inc_row.grid_columnconfigure(0, weight=1)
        self.pen_radius_inc_str = tk.StringVar(value="0.00")
        ttk.Entry(pen_inc_row, textvariable=self.pen_radius_inc_str, width=8).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(pen_inc_row, text="+", width=3,
                   command=self._pen_radius_increment).grid(row=0, column=1, padx=(0, 2))
        ttk.Button(pen_inc_row, text="-", width=3,
                   command=self._pen_radius_decrement).grid(row=0, column=2)
        row += 1

        ttk.Label(self.controls, text="Phase").grid(row=row, column=0, sticky="w")
        row += 1
        self.phase = tk.DoubleVar(value=0.0)
        self.phase_str = tk.StringVar(value=f"{self.phase.get():.2f}")
        phase_row = ttk.Frame(self.controls)
        phase_row.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        phase_row.grid_columnconfigure(0, weight=1)

        ttk.Scale(
            phase_row,
            from_=-180.0,
            to=180.0,
            variable=self.phase,
            command=self._on_phase_slider,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        phase_entry = ttk.Entry(phase_row, textvariable=self.phase_str, width=8)
        phase_entry.grid(row=0, column=1, sticky="e")
        phase_entry.bind("<Return>", self._on_phase_entry)
        phase_entry.bind("<FocusOut>", self._on_phase_entry)
        row += 1

        phase_inc_row = ttk.Frame(self.controls)
        phase_inc_row.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        phase_inc_row.grid_columnconfigure(0, weight=1)
        self.phase_inc_str = tk.StringVar(value="0.00")
        ttk.Entry(phase_inc_row, textvariable=self.phase_inc_str, width=8).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(phase_inc_row, text="+", width=3,
                   command=self._phase_increment).grid(row=0, column=1, padx=(0, 2))
        ttk.Button(phase_inc_row, text="-", width=3,
                   command=self._phase_decrement).grid(row=0, column=2)
        row += 1

        if rosette_values:
            self._on_rosette_selected()

        ttk.Separator(self.controls, orient="horizontal").grid(row=row, column=0, sticky="ew", pady=8)
        row += 1

        ttk.Button(self.controls, text="Reset View").grid(row=row, column=0, sticky="ew")
        row += 1
        ttk.Button(self.controls, text="Clear Drawing", command=self._clear_pattern).grid(
            row=row, column=0, sticky="ew", pady=(6, 0)
        )
        row += 1
        ttk.Button(self.controls, text="Delete Last", command=self._delete_last_pattern).grid(
            row=row, column=0, sticky="ew", pady=(6, 0)
        )
        row += 1
        ttk.Button(self.controls, text="Preferences", command=self._open_preferences_dialog).grid(
            row=row, column=0, sticky="ew", pady=(6, 0)
        )

    def _build_scripting_pane(self) -> None:
        self.scripting = ttk.LabelFrame(self.main_frame, text="Scripting", padding=10)
        self.scripting.grid(row=0, column=2, sticky="ns")
        self.scripting.grid_columnconfigure(0, weight=1)

        self.script_text = tk.Text(self.scripting, width=34, height=18, wrap="word")
        self.script_text.grid(row=0, column=0, sticky="nsew")

        repeats_row = ttk.Frame(self.scripting)
        repeats_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        repeats_row.grid_columnconfigure(0, weight=1)

        ttk.Label(repeats_row, text="repeats").grid(row=0, column=0, sticky="w")
        self.repeats_var = tk.StringVar(value="1")
        ttk.Entry(repeats_row, textvariable=self.repeats_var, width=8).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        ttk.Button(self.scripting, text="Execute", command=self._execute_script).grid(
            row=2, column=0, sticky="ew", pady=(10, 0)
        )

        definitions = (
            "D   Draw using current settings\n"
            "R   Change radius by the given amount\n"
            "P   Change phase by the given amount\n\n"
            "Examples:\n"
            "R-1   decrease radius by 1\n"
            "R+1.5 increase radius by 1.5\n"
            "P+10  increase phase by 10 degrees\n"
            "P-10  decrease phase by 10 degrees"
        )
        ttk.Label(self.scripting, text=definitions, justify="left", anchor="w").grid(
            row=3, column=0, sticky="ew", pady=(10, 0)
        )

    def _load_rosette_names(self) -> list[str]:
        # Populate from SVG filenames in the configured rosette directory.
        if not self.rosette_dir.exists() or not self.rosette_dir.is_dir():
            self.startup_status = f"Rosette folder not found: {self.rosette_dir}"
            self.rosette_files = {}
            return []

        svg_files = sorted(self.rosette_dir.glob("*.svg"), key=lambda p: p.name.lower())
        names: list[str] = []
        rosette_files: dict[str, Path] = {}
        for svg_file in svg_files:
            base_name = svg_file.stem
            name = base_name
            suffix = 2
            while name in rosette_files:
                name = f"{base_name} ({suffix})"
                suffix += 1

            names.append(name)
            rosette_files[name] = svg_file

        self.rosette_files = rosette_files
        return names

    def _refresh_rosette_list(self) -> None:
        current = self.rosette_var.get()
        rosette_values = self._load_rosette_names()
        self.rosette_menu.configure(values=rosette_values)
        if rosette_values:
            self.rosette_menu.state(["!disabled"])
            if current in rosette_values:
                self.rosette_var.set(current)
            else:
                self.rosette_var.set(rosette_values[0])
                self._on_rosette_selected()
        else:
            self.rosette_menu.state(["disabled"])
            self.rosette_var.set("No SVG files found")
        self._set_status(f"Rosette list refreshed ({len(rosette_values)} found)")

    def _execute_script(self) -> None:
        script = self.script_text.get("1.0", "end-1c").strip()
        if not script:
            self._set_status("No script to execute")
            return

        try:
            repeats = int(float(self.repeats_var.get().strip() or "1"))
        except ValueError:
            self._set_status("Repeats must be a number")
            return

        if repeats < 1:
            self._set_status("Repeats must be at least 1")
            return

        commands = [line.strip() for line in script.splitlines()]
        commands = [line for line in commands if line and not line.startswith("#") and not line.startswith(";")]
        if not commands:
            self._set_status("No script commands to execute")
            return

        self._stop_simulation(update_status=False)
        self.script_running = True
        self.script_commands = commands
        self.script_command_index = 0
        self.script_repeat_total = repeats
        self.script_repeat_index = 0
        self._set_status(f"Executing script ({repeats} repeat(s))")
        self._run_script_command()

    def _run_script_command(self) -> None:
        if not self.script_running:
            return

        while self.script_running:
            if self.script_command_index >= len(self.script_commands):
                self.script_repeat_index += 1
                if self.script_repeat_index >= self.script_repeat_total:
                    self.script_running = False
                    self._set_status("Script complete")
                    return

                self.script_command_index = 0
                continue

            command_text = self.script_commands[self.script_command_index]
            self.script_command_index += 1

            parsed = self._parse_script_command(command_text)
            if parsed is None:
                self.script_running = False
                self._set_status(f"Invalid script command: {command_text}")
                return

            command, value = parsed
            if command == "D":
                self._start_simulation(on_complete=self._run_script_command)
                return

            if command == "R" and value is not None:
                new_value = self._clamp(self.pen_radius.get() + value, 0.0, self.pen_radius_max)
                self.pen_radius.set(new_value)
                self.pen_radius_str.set(f"{new_value:.2f}")
                continue

            if command == "P" and value is not None:
                new_value = self._clamp(self.phase.get() + value, -180.0, 180.0)
                self.phase.set(new_value)
                self.phase_str.set(f"{new_value:.2f}")
                continue

    def _parse_script_command(self, command_text: str) -> tuple[str, float | None] | None:
        normalized = command_text.strip()
        if not normalized:
            return None

        if normalized.upper() == "D":
            return ("D", None)

        match = re.fullmatch(r"([RP])\s*([+-])\s*(\d+(?:\.\d+)?)", normalized, flags=re.IGNORECASE)
        if not match:
            return None

        command = match.group(1).upper()
        sign = 1.0 if match.group(2) == "+" else -1.0
        value = float(match.group(3)) * sign
        return (command, value)

    def _open_preferences_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("preferences")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        container = ttk.Frame(dialog, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(1, weight=1)

        rosette_dir_var = tk.StringVar(value=str(self.rosette_dir))
        zoom_var = tk.StringVar(value=f"{self.default_zoom:.2f}")
        width_var = tk.StringVar(value=f"{self.pattern_line_width:.2f}")
        color_var = tk.StringVar(value=self.pattern_line_color)

        ttk.Label(container, text="Rosette Directory").grid(row=0, column=0, sticky="w", pady=(0, 6))
        directory_row = ttk.Frame(container)
        directory_row.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        directory_row.grid_columnconfigure(0, weight=1)
        ttk.Entry(directory_row, textvariable=rosette_dir_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def browse_directory() -> None:
            selected = filedialog.askdirectory(initialdir=rosette_dir_var.get() or str(self.rosette_dir))
            if selected:
                rosette_dir_var.set(selected)

        ttk.Button(directory_row, text="Browse", command=browse_directory).grid(row=0, column=1, sticky="e")

        ttk.Label(container, text="Default Zoom").grid(row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Entry(container, textvariable=zoom_var, width=10).grid(row=1, column=1, sticky="w", pady=(0, 6))

        ttk.Label(container, text="Pattern Width").grid(row=2, column=0, sticky="w", pady=(0, 6))
        ttk.Entry(container, textvariable=width_var, width=10).grid(row=2, column=1, sticky="w", pady=(0, 6))

        ttk.Label(container, text="Pattern Color").grid(row=3, column=0, sticky="w")
        color_row = ttk.Frame(container)
        color_row.grid(row=3, column=1, sticky="ew")
        color_row.grid_columnconfigure(0, weight=1)
        ttk.Entry(color_row, textvariable=color_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def choose_color() -> None:
            _, chosen = colorchooser.askcolor(color=color_var.get(), parent=dialog, title="Choose Pattern Color")
            if chosen:
                color_var.set(chosen)

        ttk.Button(color_row, text="Pick", command=choose_color).grid(row=0, column=1, sticky="e")

        button_row = ttk.Frame(container)
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))

        def save_preferences() -> None:
            new_dir_text = rosette_dir_var.get().strip()
            if not new_dir_text:
                messagebox.showerror("preferences", "Rosette directory cannot be empty.", parent=dialog)
                return

            try:
                new_zoom = float(zoom_var.get().strip())
            except ValueError:
                messagebox.showerror("preferences", "Default zoom must be a number.", parent=dialog)
                return

            if not 0.25 <= new_zoom <= 4.0:
                messagebox.showerror("preferences", "Default zoom must be between 0.25 and 4.0.", parent=dialog)
                return

            try:
                new_width = float(width_var.get().strip())
            except ValueError:
                messagebox.showerror("preferences", "Pattern width must be a number.", parent=dialog)
                return

            if new_width <= 0:
                messagebox.showerror("preferences", "Pattern width must be greater than zero.", parent=dialog)
                return

            try:
                preview_line = self.canvas.create_line(0, 0, 1, 1, fill=color_var.get())
            except tk.TclError:
                messagebox.showerror("preferences", "Pattern color is invalid.", parent=dialog)
                return
            self.canvas.delete(preview_line)

            self.rosette_dir = Path(new_dir_text)
            self.default_zoom = new_zoom
            self.pattern_line_width = new_width
            self.pattern_line_color = color_var.get()

            self.zoom_var.set(new_zoom)
            self.zoom_text.set(f"{new_zoom:.2f}x")

            # Update already drawn patterns and active pen marker to match preferences.
            self.canvas.itemconfigure("pattern", fill=self.pattern_line_color, width=self.pattern_line_width)
            if self.pen_marker_id is not None:
                self.canvas.itemconfigure(self.pen_marker_id, fill=self.pattern_line_color)

            self._refresh_rosette_list()
            dialog.destroy()

        ttk.Button(button_row, text="Cancel", command=dialog.destroy).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(button_row, text="Save", command=save_preferences).grid(row=0, column=1)

    def _set_status(self, message: str) -> None:
        if hasattr(self, "status_text"):
            self.status_text.set(message)
        else:
            self.startup_status = message

    def _on_rosette_selected(self, _event: tk.Event | None = None) -> None:
        selected_name = self.rosette_var.get()
        svg_path = self.rosette_files.get(selected_name)
        if svg_path is None:
            return

        max_radius = self._derive_max_radius_from_svg(svg_path)
        if max_radius <= 0:
            self.amplitude_str.set("0.00")
            self._set_status(f"Could not derive radius from {svg_path.name}")
            return

        amplitude = self._derive_amplitude_from_svg(svg_path)
        self.amplitude_str.set(f"{amplitude:.2f}")

        self.current_rosette_max_radius = max_radius
        clamped_radius = self._clamp(max_radius, 0.0, self.pen_radius_max)
        self.pen_radius_scale.configure(to=self.pen_radius_max)
        snapped_radius = round(clamped_radius)
        self.pen_radius.set(snapped_radius)
        self.pen_radius_str.set(f"{snapped_radius:.2f}")
        self._set_status(
            f"Loaded {svg_path.name} (derived radius {max_radius:.3f}, set to {clamped_radius:.3f} mm)"
        )

    def _derive_max_radius_from_svg(self, svg_path: Path) -> float:
        center, points = self._load_svg_center_and_points(svg_path)
        center_x, center_y = center
        if not points:
            return 0.0

        return max(math.hypot(x - center_x, y - center_y) for x, y in points)

    def _derive_amplitude_from_svg(self, svg_path: Path) -> float:
        center, points = self._load_svg_center_and_points(svg_path)
        center_x, center_y = center
        if not points:
            return 0.0

        radii = [math.hypot(x - center_x, y - center_y) for x, y in points]
        return max(radii) - min(radii)

    def _load_svg_center_and_points(self, svg_path: Path) -> tuple[tuple[float, float], list[tuple[float, float]]]:
        try:
            root = ET.parse(svg_path).getroot()
        except (ET.ParseError, OSError):
            return (0.0, 0.0), []

        fallback_center_x, fallback_center_y = self._derive_svg_center(root)
        points: list[tuple[float, float]] = []

        for element in root.iter():
            tag = element.tag.split("}")[-1]

            if tag == "circle":
                cx = self._to_float(element.get("cx"), 0.0)
                cy = self._to_float(element.get("cy"), 0.0)
                r = self._to_float(element.get("r"), 0.0)
                points.extend(self._sample_ellipse_points(cx, cy, r, r))
                continue

            if tag == "ellipse":
                cx = self._to_float(element.get("cx"), 0.0)
                cy = self._to_float(element.get("cy"), 0.0)
                rx = self._to_float(element.get("rx"), 0.0)
                ry = self._to_float(element.get("ry"), 0.0)
                points.extend(self._sample_ellipse_points(cx, cy, rx, ry))
                continue

            points.extend(self._extract_points_from_element(tag, element))

        if points:
            center_x, center_y = self._derive_polar_center(points, (fallback_center_x, fallback_center_y))
            return (center_x, center_y), points

        points.append((fallback_center_x, fallback_center_y))
        return (fallback_center_x, fallback_center_y), points

    def _derive_polar_center(
        self, points: list[tuple[float, float]], fallback: tuple[float, float]
    ) -> tuple[float, float]:
        # Fit a circle center to the sampled rosette points for radial centering.
        if len(points) < 3:
            return fallback

        mean_x = sum(point[0] for point in points) / len(points)
        mean_y = sum(point[1] for point in points) / len(points)

        suu = 0.0
        suv = 0.0
        svv = 0.0
        suuu = 0.0
        svvv = 0.0
        suvv = 0.0
        svuu = 0.0

        for x, y in points:
            u = x - mean_x
            v = y - mean_y
            uu = u * u
            vv = v * v

            suu += uu
            suv += u * v
            svv += vv
            suuu += uu * u
            svvv += vv * v
            suvv += u * vv
            svuu += v * uu

        det = (suu * svv) - (suv * suv)
        if abs(det) < 1e-12:
            return fallback

        rhs_u = 0.5 * (suuu + suvv)
        rhs_v = 0.5 * (svvv + svuu)

        uc = ((rhs_u * svv) - (rhs_v * suv)) / det
        vc = ((suu * rhs_v) - (suv * rhs_u)) / det

        return (mean_x + uc, mean_y + vc)

    def _sample_ellipse_points(
        self, cx: float, cy: float, rx: float, ry: float, segments: int = 180
    ) -> list[tuple[float, float]]:
        sampled: list[tuple[float, float]] = []
        if rx <= 0 or ry <= 0:
            return sampled

        for index in range(segments):
            angle = (2 * math.pi * index) / segments
            sampled.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
        return sampled

    def _derive_svg_center(self, root: ET.Element) -> tuple[float, float]:
        view_box = root.get("viewBox")
        if view_box:
            parts = [self._to_float(value) for value in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", view_box)]
            if len(parts) >= 4:
                min_x, min_y, width, height = parts[:4]
                return (min_x + width / 2.0, min_y + height / 2.0)

        width = self._to_float(root.get("width"))
        height = self._to_float(root.get("height"))
        if width > 0 and height > 0:
            return (width / 2.0, height / 2.0)

        return (0.0, 0.0)

    def _extract_points_from_element(self, tag: str, element: ET.Element) -> list[tuple[float, float]]:
        if tag == "line":
            x1 = self._to_float(element.get("x1"), 0.0)
            y1 = self._to_float(element.get("y1"), 0.0)
            x2 = self._to_float(element.get("x2"), 0.0)
            y2 = self._to_float(element.get("y2"), 0.0)
            return [(x1, y1), (x2, y2)]

        if tag in ("polyline", "polygon"):
            return self._parse_point_list(element.get("points", ""))

        if tag == "rect":
            x = self._to_float(element.get("x"), 0.0)
            y = self._to_float(element.get("y"), 0.0)
            width = self._to_float(element.get("width"), 0.0)
            height = self._to_float(element.get("height"), 0.0)
            return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]

        if tag == "path":
            return self._parse_path_points(element.get("d", ""))

        return []

    def _parse_point_list(self, points_text: str) -> list[tuple[float, float]]:
        values = [self._to_float(v) for v in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", points_text)]
        points: list[tuple[float, float]] = []
        for i in range(0, len(values) - 1, 2):
            points.append((values[i], values[i + 1]))
        return points

    def _parse_path_points(self, path_data: str) -> list[tuple[float, float]]:
        token_pattern = r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
        tokens = re.findall(token_pattern, path_data)
        if not tokens:
            return []

        points: list[tuple[float, float]] = []
        index = 0
        command = ""
        current_x, current_y = 0.0, 0.0
        start_x, start_y = 0.0, 0.0

        def is_command(value: str) -> bool:
            return len(value) == 1 and value.isalpha()

        def next_numbers(count: int) -> list[float] | None:
            nonlocal index
            if index + count > len(tokens):
                return None
            values: list[float] = []
            for offset in range(count):
                token = tokens[index + offset]
                if is_command(token):
                    return None
                values.append(float(token))
            index += count
            return values

        while index < len(tokens):
            token = tokens[index]
            if is_command(token):
                command = token
                index += 1
            elif not command:
                index += 1
                continue

            if command in ("M", "m"):
                values = next_numbers(2)
                if values is None:
                    continue
                x, y = values
                if command == "m":
                    x += current_x
                    y += current_y
                current_x, current_y = x, y
                start_x, start_y = x, y
                points.append((x, y))
                while True:
                    values = next_numbers(2)
                    if values is None:
                        break
                    x, y = values
                    if command == "m":
                        x += current_x
                        y += current_y
                    current_x, current_y = x, y
                    points.append((x, y))
                continue

            if command in ("L", "l"):
                while True:
                    values = next_numbers(2)
                    if values is None:
                        break
                    x, y = values
                    if command == "l":
                        x += current_x
                        y += current_y
                    current_x, current_y = x, y
                    points.append((x, y))
                continue

            if command in ("H", "h"):
                while True:
                    values = next_numbers(1)
                    if values is None:
                        break
                    x = values[0] + current_x if command == "h" else values[0]
                    current_x = x
                    points.append((current_x, current_y))
                continue

            if command in ("V", "v"):
                while True:
                    values = next_numbers(1)
                    if values is None:
                        break
                    y = values[0] + current_y if command == "v" else values[0]
                    current_y = y
                    points.append((current_x, current_y))
                continue

            if command in ("C", "c"):
                while True:
                    values = next_numbers(6)
                    if values is None:
                        break
                    x1, y1, x2, y2, x, y = values
                    if command == "c":
                        x1 += current_x
                        y1 += current_y
                        x2 += current_x
                        y2 += current_y
                        x += current_x
                        y += current_y
                    points.extend([(x1, y1), (x2, y2), (x, y)])
                    current_x, current_y = x, y
                continue

            if command in ("S", "s"):
                while True:
                    values = next_numbers(4)
                    if values is None:
                        break
                    x2, y2, x, y = values
                    if command == "s":
                        x2 += current_x
                        y2 += current_y
                        x += current_x
                        y += current_y
                    points.extend([(x2, y2), (x, y)])
                    current_x, current_y = x, y
                continue

            if command in ("Q", "q"):
                while True:
                    values = next_numbers(4)
                    if values is None:
                        break
                    x1, y1, x, y = values
                    if command == "q":
                        x1 += current_x
                        y1 += current_y
                        x += current_x
                        y += current_y
                    points.extend([(x1, y1), (x, y)])
                    current_x, current_y = x, y
                continue

            if command in ("T", "t"):
                while True:
                    values = next_numbers(2)
                    if values is None:
                        break
                    x, y = values
                    if command == "t":
                        x += current_x
                        y += current_y
                    points.append((x, y))
                    current_x, current_y = x, y
                continue

            if command in ("A", "a"):
                while True:
                    values = next_numbers(7)
                    if values is None:
                        break
                    _, _, _, _, _, x, y = values
                    if command == "a":
                        x += current_x
                        y += current_y
                    points.append((x, y))
                    current_x, current_y = x, y
                continue

            if command in ("Z", "z"):
                current_x, current_y = start_x, start_y
                points.append((current_x, current_y))
                continue

        return points

    def _to_float(self, value: str | None, default: float = 0.0) -> float:
        if value is None:
            return default
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
        if not match:
            return default
        try:
            return float(match.group(0))
        except ValueError:
            return default

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    def _on_pen_radius_slider(self, _value: str) -> None:
        snapped_value = self._clamp(round(float(_value)), 0.0, self.pen_radius_max)
        if abs(self.pen_radius.get() - snapped_value) > 1e-9:
            self.pen_radius.set(snapped_value)
        self.pen_radius_str.set(f"{snapped_value:.2f}")

    def _on_pen_radius_entry(self, _event: tk.Event) -> None:
        try:
            value = float(self.pen_radius_str.get())
        except ValueError:
            self.pen_radius_str.set(f"{self.pen_radius.get():.2f}")
            return

        value = self._clamp(value, 0.0, self.pen_radius_max)
        self.pen_radius.set(value)
        self.pen_radius_str.set(f"{value:.2f}")

    def _start_simulation(self, on_complete=None) -> None:
        if self.simulation_running:
            self._stop_simulation(update_status=False)

        if self.pen_marker_id is not None:
            self.canvas.delete(self.pen_marker_id)
            self.pen_marker_id = None

        self.simulation_complete_callback = on_complete

        selected_name = self.rosette_var.get()
        svg_path = self.rosette_files.get(selected_name)
        if svg_path is None:
            self._set_status("No rosette selected")
            return

        points = self._build_simulation_points(svg_path)
        if len(points) < 2:
            self._set_status(f"Unable to draw pattern from {selected_name}")
            return

        self.simulation_points = points + [points[0]]
        self.simulation_index = 1
        self.simulation_running = True
        self.start_button.state(["disabled"])
        self.stop_button.state(["!disabled"])

        self.pattern_run_counter += 1
        self.pattern_tag = f"pat_{self.pattern_run_counter}"
        self.drawn_patterns.append((self.pattern_tag, self.simulation_vectors.copy()))

        first_x, first_y = self.simulation_points[0]
        self.pen_marker_id = self.canvas.create_oval(
            first_x - 3,
            first_y - 3,
            first_x + 3,
            first_y + 3,
            fill=self.pattern_line_color,
            outline="",
            tags="pen-marker",
        )

        self._set_status(f"Drawing {selected_name}...")
        self._draw_simulation_step()

    def _build_simulation_points(self, svg_path: Path) -> list[tuple[float, float]]:
        center, raw_points = self._load_svg_center_and_points(svg_path)
        if not raw_points:
            return []

        center_x, center_y = center
        vectors = [(x - center_x, y - center_y) for x, y in raw_points]
        radii = [math.hypot(dx, dy) for dx, dy in vectors]
        svg_max_radius = max(radii) if radii else 0.0
        if svg_max_radius <= 0:
            return []

        self.current_rosette_max_radius = svg_max_radius
        pen_radius_mm = self._clamp(self.pen_radius.get(), 0.0, self.pen_radius_max)
        radial_offset = pen_radius_mm - svg_max_radius
        shifted_vectors: list[tuple[float, float]] = []
        shifted_radii: list[float] = []
        for dx, dy in vectors:
            radius = math.hypot(dx, dy)
            angle = math.atan2(dy, dx)
            shifted_radius = max(0.0, radius + radial_offset)
            shifted_vectors.append((shifted_radius * math.cos(angle), shifted_radius * math.sin(angle)))
            shifted_radii.append(shifted_radius)

        max_radius_index = shifted_radii.index(max(shifted_radii))
        phase_degrees = self._clamp(self.phase.get(), -180.0, 180.0)
        phase_index_shift = int(len(shifted_vectors) * (phase_degrees / 360.0))
        start_index = (max_radius_index + phase_index_shift) % len(shifted_vectors)
        ordered_vectors = shifted_vectors[start_index:] + shifted_vectors[:start_index]

        # Rotate so the first point always starts at middle-left (180 degrees).
        if ordered_vectors:
            start_dx, start_dy = ordered_vectors[0]
            start_angle = math.atan2(start_dy, start_dx)
            rotate_angle = math.pi - start_angle
            cos_a = math.cos(rotate_angle)
            sin_a = math.sin(rotate_angle)
            ordered_vectors = [
                (dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a) for dx, dy in ordered_vectors
            ]

        self.simulation_vectors = ordered_vectors
        return self._project_vectors_to_canvas(ordered_vectors)

    def _project_vectors_to_canvas(self, vectors: list[tuple[float, float]]) -> list[tuple[float, float]]:
        canvas_width = max(10, int(self.canvas.winfo_width()))
        canvas_height = max(10, int(self.canvas.winfo_height()))
        canvas_center_x = canvas_width / 2
        canvas_center_y = canvas_height / 2
        canvas_radius = (min(canvas_width, canvas_height) / 2) - 16
        zoom = self._clamp(self.zoom_var.get(), 0.25, 4.0)
        mm_to_pixels = (canvas_radius / self.pen_radius_max) * zoom if self.pen_radius_max > 0 else 1.0

        return [
            (canvas_center_x + (dx * mm_to_pixels), canvas_center_y - (dy * mm_to_pixels))
            for dx, dy in vectors
        ]

    def _draw_simulation_step(self) -> None:
        if not self.simulation_running or self.pattern_tag is None:
            return

        step_points = 8
        new_index = min(self.simulation_index + step_points, len(self.simulation_points))

        # Draw a small segment from the last drawn point to the new position — O(1) per frame.
        chunk = self.simulation_points[self.simulation_index - 1 : new_index]
        if len(chunk) >= 2:
            coords: list[float] = [v for pt in chunk for v in pt]
            self.canvas.create_line(
                *coords,
                fill=self.pattern_line_color,
                width=self.pattern_line_width,
                tags=("pattern", self.pattern_tag),
            )

        self.simulation_index = new_index

        if self.pen_marker_id is not None:
            current_x, current_y = self.simulation_points[self.simulation_index - 1]
            self.canvas.coords(
                self.pen_marker_id,
                current_x - 3,
                current_y - 3,
                current_x + 3,
                current_y + 3,
            )

        if self.simulation_index >= len(self.simulation_points):
            completion_callback = self.simulation_complete_callback
            self.simulation_complete_callback = None
            self.simulation_running = False
            self.simulation_after_id = None
            self.start_button.state(["!disabled"])
            self.stop_button.state(["disabled"])
            if self.pen_marker_id is not None:
                self.canvas.delete(self.pen_marker_id)
                self.pen_marker_id = None
            self._set_status("Pattern complete")
            if completion_callback is not None:
                completion_callback()
            return

        self.simulation_after_id = self.after(12, self._draw_simulation_step)

    def _stop_simulation(self, update_status: bool = True) -> None:
        if self.simulation_after_id is not None:
            self.after_cancel(self.simulation_after_id)
            self.simulation_after_id = None
        self.simulation_complete_callback = None
        self.simulation_running = False
        self.start_button.state(["!disabled"])
        self.stop_button.state(["disabled"])
        if update_status:
            self._set_status("Simulation stopped")

    def _clear_pattern(self) -> None:
        self._stop_simulation(update_status=False)
        self.canvas.delete("pattern")
        self.canvas.delete("pen-marker")
        self.pattern_tag = None
        self.pen_marker_id = None
        self.simulation_vectors = []
        self.simulation_points = []
        self.simulation_index = 0
        self.drawn_patterns.clear()
        if self.rosette_var.get() in self.rosette_files:
            self._on_rosette_selected()
        self.phase.set(0.0)
        self.phase_str.set("0.00")
        self._set_status("Drawing cleared")

    def _delete_last_pattern(self) -> None:
        if not self.drawn_patterns:
            self._set_status("No pattern to delete")
            return

        last_tag, _ = self.drawn_patterns.pop()
        self.canvas.delete(last_tag)

        if self.pattern_tag == last_tag:
            self._stop_simulation(update_status=False)
            if self.pen_marker_id is not None:
                self.canvas.delete(self.pen_marker_id)
                self.pen_marker_id = None

            self.pattern_tag = None
            self.simulation_points = []
            self.simulation_vectors = []
            self.simulation_index = 0

        self._set_status("Deleted last pattern")

    def _on_zoom_changed(self, value: str) -> None:
        zoom = self._clamp(float(value), 0.25, 4.0)
        self.zoom_text.set(f"{zoom:.2f}x")
        self._draw_placeholder_guides()
        self._reproject_pattern()

    def _reproject_pattern(self) -> None:
        if not self.drawn_patterns:
            return

        for tag, vectors in self.drawn_patterns:
            reprojected = self._project_vectors_to_canvas(vectors)
            if not reprojected:
                continue

            all_points = reprojected + [reprojected[0]]

            # Delete all existing segments for this pattern and redraw as one polyline.
            self.canvas.delete(tag)

            is_active = tag == self.pattern_tag and self.simulation_running
            draw_points = all_points[: self.simulation_index] if is_active else all_points

            if len(draw_points) >= 2:
                coords: list[float] = [v for pt in draw_points for v in pt]
                self.canvas.create_line(
                    *coords,
                    fill=self.pattern_line_color,
                    width=self.pattern_line_width,
                    tags=("pattern", tag),
                )

            if is_active:
                self.simulation_points = all_points

        if self.pen_marker_id is not None and self.simulation_index > 0 and self.simulation_points:
            current_x, current_y = self.simulation_points[self.simulation_index - 1]
            self.canvas.coords(
                self.pen_marker_id,
                current_x - 3,
                current_y - 3,
                current_x + 3,
                current_y + 3,
            )

    def _pen_radius_increment(self) -> None:
        try:
            inc = float(self.pen_radius_inc_str.get())
        except ValueError:
            return
        new_val = self._clamp(self.pen_radius.get() + inc, 0.0, self.pen_radius_max)
        self.pen_radius.set(new_val)
        self.pen_radius_str.set(f"{new_val:.2f}")

    def _pen_radius_decrement(self) -> None:
        try:
            inc = float(self.pen_radius_inc_str.get())
        except ValueError:
            return
        new_val = self._clamp(self.pen_radius.get() - inc, 0.0, self.pen_radius_max)
        self.pen_radius.set(new_val)
        self.pen_radius_str.set(f"{new_val:.2f}")

    def _phase_increment(self) -> None:
        try:
            inc = float(self.phase_inc_str.get())
        except ValueError:
            return
        new_val = self._clamp(self.phase.get() + inc, -180.0, 180.0)
        self.phase.set(new_val)
        self.phase_str.set(f"{new_val:.2f}")

    def _phase_decrement(self) -> None:
        try:
            inc = float(self.phase_inc_str.get())
        except ValueError:
            return
        new_val = self._clamp(self.phase.get() - inc, -180.0, 180.0)
        self.phase.set(new_val)
        self.phase_str.set(f"{new_val:.2f}")

    def _on_phase_slider(self, _value: str) -> None:
        self.phase_str.set(f"{self.phase.get():.2f}")

    def _on_phase_entry(self, _event: tk.Event) -> None:
        try:
            value = float(self.phase_str.get())
        except ValueError:
            self.phase_str.set(f"{self.phase.get():.2f}")
            return

        value = self._clamp(value, -180.0, 180.0)
        self.phase.set(value)
        self.phase_str.set(f"{value:.2f}")

    def _build_status_bar(self) -> None:
        self.status_text = tk.StringVar(value=self.startup_status)
        ttk.Label(self.status_frame, textvariable=self.status_text, anchor="w").grid(
            row=0, column=0, sticky="ew"
        )

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        self._draw_placeholder_guides()
        self._reproject_pattern()

    def _draw_placeholder_guides(self) -> None:
        # Draw a simple polar grid to visualize angular positioning.
        self.canvas.delete("grid")
        width = int(self.canvas.winfo_width())
        height = int(self.canvas.winfo_height())
        if width < 10 or height < 10:
            return

        center_x = width // 2
        center_y = height // 2
        zoom = self._clamp(self.zoom_var.get(), 0.25, 4.0)
        radius = ((min(width, height) / 2) - 12) * zoom

        # Concentric circles.
        for factor in (0.25, 0.5, 0.75, 1.0):
            r = radius * factor
            self.canvas.create_oval(
                center_x - r,
                center_y - r,
                center_x + r,
                center_y + r,
                outline="#d9d9d9",
                tags="grid",
            )

        # Radial lines every 45 degrees.
        for degrees in range(0, 360, 45):
            angle = math.radians(degrees)
            x = center_x + radius * math.cos(angle)
            y = center_y - radius * math.sin(angle)
            self.canvas.create_line(center_x, center_y, x, y, fill="#d0d0d0", tags="grid")

        self.canvas.create_oval(
            center_x - 3,
            center_y - 3,
            center_x + 3,
            center_y + 3,
            fill="#8a8a8a",
            outline="",
            tags="grid",
        )

        self.canvas.create_text(
            12,
            12,
            anchor="nw",
            text="Pen chuck drawing canvas",
            fill="#555555",
            font=("Segoe UI", 10, "bold"),
            tags="grid",
        )


def main() -> None:
    app = PenChuckApp()
    app.mainloop()


if __name__ == "__main__":
    main()
