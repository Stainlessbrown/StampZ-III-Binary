from pathlib import Path

path = Path(__file__).resolve().parent / "sample_results_manager.py"
source = path.read_text()

anchor = "            if stddev_text:\n"
assert source.count(anchor) == 1, "Expected sample insertion point not unique"

addition = '''            # LCh readouts: derived from existing analytical/display Lab.
            # No changes to averaging, Delta E, or stored measurements.
            from utils.user_preferences import get_preferences_manager
            from utils.lab_difference import lab_to_lch

            if get_preferences_manager().get_export_include_lch():
                for heading, lab_values in (
                    ("LCh — Analytical", lab),
                    ("LCh — Rendered*", display_lab),
                ):
                    if lab_values is None:
                        continue
                    L, C, h = lab_to_lch(lab_values)
                    ttk.Label(
                        controls_frame,
                        text=heading,
                        font=("Arial", 10, "bold"),
                    ).pack(anchor="w", pady=(5, 0))

                    ttk.Label(
                        controls_frame,
                        text=f"L*: {L:.3f}   C*: {C:.3f}   h°: {h:.3f}",
                        font=("Arial", 10),
                    ).pack(anchor="w")

'''

updated = source.replace(anchor, addition + anchor, 1)
compile(updated, str(path), "exec")
path.write_text(updated)

print("SUCCESS: Individual sample LCh readouts added.")