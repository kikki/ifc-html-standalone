from __future__ import annotations

import queue
import sys
import threading
from datetime import date
from pathlib import Path

import dearpygui.dearpygui as dpg

from .core import ViewerOptions, convert, validate_ifc


class GeneratorApp:
    """English native desktop interface for the portable IFC HTML generator."""

    def __init__(self) -> None:
        self.files: list[Path] = []
        self.reports: dict[Path, dict] = {}
        self.row_tags: dict[Path, tuple[str, str]] = {}
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self._next_row = 0
        self._build_ui()

    def _build_ui(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="IFC HTML Generator", width=980, height=760, min_width=820, min_height=640)

        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._add_dialog_callback,
            tag="add_ifc_dialog",
            width=760,
            height=500,
            modal=True,
        ):
            dpg.add_file_extension(".ifc", color=(70, 170, 255, 255), custom_text="IFC")
            dpg.add_file_extension(".*")

        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._save_dialog_callback,
            tag="save_html_dialog",
            width=760,
            height=500,
            modal=True,
        ):
            dpg.add_file_extension(".html", color=(70, 170, 255, 255), custom_text="HTML")

        with dpg.window(tag="primary_window", label="IFC HTML Generator", no_close=True):
            dpg.add_text("IFC HTML Generator", color=(230, 238, 248), tag="heading")
            dpg.add_text("Create one fully offline HTML viewer from one or more validated IFC models.")
            dpg.add_spacer(height=6)

            with dpg.collapsing_header(label="Viewer settings", default_open=True):
                with dpg.group(horizontal=True):
                    dpg.add_text("Viewer title", bullet=True)
                    dpg.add_input_text(
                        tag="viewer_title",
                        default_value="Free HTML Model Viewer",
                        width=-1,
                    )
                with dpg.group(horizontal=True):
                    dpg.add_text("Prepared by (optional)", bullet=True)
                    dpg.add_input_text(tag="prepared_by", width=-1)
                with dpg.group(horizontal=True):
                    dpg.add_text("Creation date", bullet=True)
                    dpg.add_input_text(
                        tag="creation_date",
                        default_value=date.today().isoformat(),
                        readonly=True,
                        width=160,
                    )
                    dpg.add_spacer(width=30)
                    dpg.add_text("Flight speed", bullet=True)
                    dpg.add_input_float(
                        tag="flight_speed",
                        default_value=5.0,
                        min_value=0.5,
                        max_value=50.0,
                        min_clamped=True,
                        max_clamped=True,
                        step=0.5,
                        format="%.1f",
                        width=120,
                    )
                dpg.add_text(
                    "Always included: Created and distributed by waabe.de · n.rube@waabe.de",
                    color=(155, 165, 178),
                )

            dpg.add_spacer(height=6)
            dpg.add_text("IFC models and preflight checks")
            with dpg.table(
                tag="models_table",
                header_row=True,
                resizable=True,
                policy=dpg.mvTable_SizingStretchProp,
                scrollY=True,
                height=300,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
            ):
                dpg.add_table_column(label="Remove", width_fixed=True, init_width_or_weight=65)
                dpg.add_table_column(label="IFC file", init_width_or_weight=4.0)
                dpg.add_table_column(label="Schema", init_width_or_weight=1.0)
                dpg.add_table_column(label="Products", init_width_or_weight=1.0)
                dpg.add_table_column(label="Preflight status", init_width_or_weight=1.8)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Add IFC models...", callback=lambda: dpg.show_item("add_ifc_dialog"), tag="add_button")
                dpg.add_button(label="Remove selected", callback=self.remove_selected, tag="remove_button")
                dpg.add_button(label="Clear", callback=self.clear_models, tag="clear_button")

            dpg.add_spacer(height=6)
            dpg.add_text(
                "Each IFC is opened with IfcOpenShell before conversion. The schema, IfcProject, "
                "product count and spatial structure are checked. The final HTML is checked for "
                "offline safety and valid embedded model data.",
                wrap=900,
                color=(155, 165, 178),
            )
            dpg.add_spacer(height=8)
            with dpg.group(horizontal=True):
                dpg.add_text("Add one or more IFC models.", tag="status_text")
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="Create standalone HTML...",
                    callback=self.prepare_create_html,
                    tag="create_button",
                    width=220,
                )

        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("primary_window", True)
        dpg.set_frame_callback(1, self._process_events)

    def run(self) -> None:
        dpg.start_dearpygui()
        dpg.destroy_context()

    def _add_dialog_callback(self, sender: int | str, app_data: dict, user_data: object = None) -> None:
        selections = app_data.get("selections", {}) if isinstance(app_data, dict) else {}
        paths = [Path(value).resolve() for value in selections.values()]
        if not paths and isinstance(app_data, dict) and app_data.get("file_path_name"):
            paths = [Path(app_data["file_path_name"]).resolve()]
        self.add_models(paths)

    def add_models(self, paths: list[Path]) -> None:
        failures: list[str] = []
        for path in paths:
            if path in self.files:
                continue
            dpg.set_value("status_text", f"Checking {path.name}...")
            dpg.render_dearpygui_frame()
            try:
                report = validate_ifc(path)
            except Exception as error:
                failures.append(f"{path.name}: {error}")
                continue
            self.files.append(path)
            self.reports[path] = report
            self._next_row += 1
            row_tag = f"model_row_{self._next_row}"
            check_tag = f"model_check_{self._next_row}"
            spatial_class = report.get("spatialClass")
            preflight_text = (
                f"Loaded — {spatial_class}"
                if spatial_class
                else "Loaded — spatial count skipped"
            )
            preflight_color = (80, 200, 120) if spatial_class else (235, 185, 80)
            with dpg.table_row(parent="models_table", tag=row_tag):
                dpg.add_checkbox(tag=check_tag)
                dpg.add_text(str(path))
                dpg.add_text(str(report["schema"]))
                dpg.add_text(f"{report['products']:,}")
                dpg.add_text(preflight_text, color=preflight_color)
            self.row_tags[path] = (row_tag, check_tag)
        self._update_ready_status()
        if failures:
            self.show_modal(
                "IFC preflight failed",
                "The following files were not added:\n\n" + "\n".join(failures),
                error=True,
            )

    def remove_selected(self) -> None:
        selected = [path for path, (_, check) in self.row_tags.items() if dpg.get_value(check)]
        for path in selected:
            row, _ = self.row_tags.pop(path)
            if dpg.does_item_exist(row):
                dpg.delete_item(row)
            if path in self.files:
                self.files.remove(path)
            self.reports.pop(path, None)
        self._update_ready_status()

    def clear_models(self) -> None:
        for row, _ in self.row_tags.values():
            if dpg.does_item_exist(row):
                dpg.delete_item(row)
        self.files.clear()
        self.reports.clear()
        self.row_tags.clear()
        dpg.set_value("status_text", "Add one or more IFC models.")

    def _update_ready_status(self) -> None:
        dpg.set_value("status_text", f"{len(self.files)} validated IFC model(s) ready.")

    def _viewer_options(self) -> ViewerOptions:
        return ViewerOptions(
            title=str(dpg.get_value("viewer_title")),
            prepared_by=str(dpg.get_value("prepared_by")),
            flight_speed=float(dpg.get_value("flight_speed")),
            creation_date=str(dpg.get_value("creation_date")),
        ).normalized()

    def prepare_create_html(self) -> None:
        if self.busy:
            return
        if not self.files:
            self.show_modal("No IFC models", "Add at least one valid IFC model.", error=True)
            return
        try:
            options = self._viewer_options()
        except Exception as error:
            self.show_modal("Invalid viewer settings", str(error), error=True)
            return
        dpg.configure_item("save_html_dialog", default_filename=re_safe_filename(options.title) + ".html")
        dpg.show_item("save_html_dialog")

    def _save_dialog_callback(self, sender: int | str, app_data: dict, user_data: object = None) -> None:
        if not isinstance(app_data, dict) or not app_data.get("file_path_name"):
            return
        output = Path(app_data["file_path_name"])
        if output.suffix.lower() != ".html":
            output = output.with_suffix(".html")
        try:
            options = self._viewer_options()
        except Exception as error:
            self.show_modal("Invalid viewer settings", str(error), error=True)
            return
        self._set_busy(True)
        threading.Thread(
            target=self._conversion_worker,
            args=(list(self.files), output, options),
            daemon=True,
        ).start()

    def _conversion_worker(self, files: list[Path], output: Path, options: ViewerOptions) -> None:
        try:
            result = convert(
                files,
                output,
                options=options,
                progress=lambda message: self.events.put(("progress", message)),
            )
            self.events.put(("success", result))
        except Exception as error:
            self.events.put(("error", error))

    def _process_events(self, sender: int | str = 0, app_data: object = None, user_data: object = None) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "progress":
                    dpg.set_value("status_text", str(payload))
                elif event == "success":
                    self._set_busy(False)
                    self._show_success(payload)  # type: ignore[arg-type]
                elif event == "error":
                    self._set_busy(False)
                    dpg.set_value("status_text", "Creation failed.")
                    self.show_modal("HTML creation failed", str(payload), error=True)
        except queue.Empty:
            pass
        if dpg.is_dearpygui_running():
            dpg.set_frame_callback(dpg.get_frame_count() + 1, self._process_events)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for tag in (
            "viewer_title",
            "prepared_by",
            "flight_speed",
            "add_button",
            "remove_button",
            "clear_button",
            "create_button",
        ):
            dpg.configure_item(tag, enabled=not busy)

    def _show_success(self, result: dict) -> None:
        validation = result["validation"]
        schema_counts: dict[str, int] = {}
        for check in result.get("ifcChecks", []):
            schema = str(check.get("schema", "Unknown"))
            schema_counts[schema] = schema_counts.get(schema, 0) + 1
        schema_summary = ", ".join(
            f"{schema}: {count}" for schema, count in sorted(schema_counts.items())
        ) or "Unknown"
        message = (
            "Standalone HTML created successfully.\n\n"
            f"File: {result['output']}\n"
            f"IFC models: {result['models']} (all loaded successfully)\n"
            f"Detected schemas: {schema_summary}\n"
            f"Output size: {result['bytes']:,} bytes\n"
            f"Geometry fallbacks: {result['geometryFallbacks']}\n"
            f"Warnings: {result['warnings']}\n\n"
            "Final verification passed:\n- "
            + "\n- ".join(validation["checks"])
        )
        dpg.set_value("status_text", "HTML viewer created and validated successfully.")
        self.show_modal("HTML creation complete", message)

    def show_modal(self, title: str, message: str, *, error: bool = False) -> None:
        tag = "application_modal"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        with dpg.window(
            label=title,
            tag=tag,
            modal=True,
            no_resize=True,
            no_collapse=True,
            width=680,
            height=360,
            pos=(140, 140),
        ):
            dpg.add_text(message, wrap=640, color=(255, 130, 130) if error else (220, 230, 240))
            dpg.add_spacer(height=12)
            dpg.add_button(label="OK", width=100, callback=lambda: dpg.delete_item(tag))


def re_safe_filename(value: str) -> str:
    invalid = '<>:"/\\|?*'
    result = "".join("_" if char in invalid else char for char in value).strip().rstrip(".")
    return result or "IFC_Model_Viewer"


def package_self_test() -> int:
    """Lightweight packaged-resource test used by the portable build script."""

    from .core import _node_executable, _resource

    required = [
        _node_executable(),
        _resource("dist", "viewer.js"),
        _resource("dist", "worker.js"),
        _resource("src", "node", "convert-ifc.mjs"),
        _resource("node_modules", "web-ifc", "web-ifc-node.wasm"),
    ]
    return 0 if all(path.is_file() for path in required) else 2


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--self-test"]:
        return package_self_test()
    if arguments and arguments[0] == "--convert":
        from .cli import main as cli_main

        return cli_main(arguments[1:])
    app = GeneratorApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
