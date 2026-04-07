"""
db_groups.py — User-defined group management for Color Analysis databases.

Groups are stored as groups.json in the same directory as the databases:
{
    "color_analysis": {
        "Mouchon Series": ["117_AVG", "118_AVG"],
        "French Republic": ["1900_Blancs_AVG"]
    }
}

Items not listed in any group are shown under "Ungrouped".
"""

import json
import os
from typing import Dict, List, Optional
from pathlib import Path


GROUPS_FILE = "groups.json"
DEFAULT_SECTION = "color_analysis"


class GroupsManager:
    """Manages user-defined groups for Color Analysis databases."""

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Directory containing the .db files (color_analysis dir).
        """
        self.data_dir = data_dir
        self.groups_path = os.path.join(data_dir, GROUPS_FILE)
        self._data: Dict[str, Dict[str, List[str]]] = {}
        self._load()

    # ── I/O ────────────────────────────────────────────────────────────────

    def _load(self):
        """Load groups from disk, or start with empty structure."""
        try:
            if os.path.exists(self.groups_path):
                with open(self.groups_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception as e:
            print(f"GroupsManager: could not load {self.groups_path}: {e}")
            self._data = {}

    def _save(self):
        """Persist groups to disk."""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.groups_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"GroupsManager: could not save {self.groups_path}: {e}")

    # ── Public API ─────────────────────────────────────────────────────────

    def get_groups(self) -> Dict[str, List[str]]:
        """Return the {group_name: [db_name, ...]} dict for color_analysis."""
        return dict(self._data.get(DEFAULT_SECTION, {}))

    def get_group_for(self, db_name: str) -> Optional[str]:
        """Return the group name for a given db_name, or None if ungrouped."""
        for group, members in self._data.get(DEFAULT_SECTION, {}).items():
            if db_name in members:
                return group
        return None

    def set_group(self, db_name: str, group_name: str):
        """Assign db_name to group_name, removing it from any previous group."""
        section = self._data.setdefault(DEFAULT_SECTION, {})
        # Remove from existing group
        for members in section.values():
            if db_name in members:
                members.remove(db_name)
        # Add to new group (create if needed)
        section.setdefault(group_name, []).append(db_name)
        # Clean up empty groups
        self._data[DEFAULT_SECTION] = {
            k: v for k, v in section.items() if v
        }
        self._save()

    def remove_from_group(self, db_name: str):
        """Remove db_name from any group (moves it to Ungrouped)."""
        section = self._data.get(DEFAULT_SECTION, {})
        for members in section.values():
            if db_name in members:
                members.remove(db_name)
        # Clean up empty groups
        self._data[DEFAULT_SECTION] = {
            k: v for k, v in section.items() if v
        }
        self._save()

    def rename_group(self, old_name: str, new_name: str):
        """Rename a group."""
        section = self._data.get(DEFAULT_SECTION, {})
        if old_name in section:
            section[new_name] = section.pop(old_name)
            self._save()

    def delete_group(self, group_name: str):
        """Delete a group (members become ungrouped)."""
        section = self._data.get(DEFAULT_SECTION, {})
        section.pop(group_name, None)
        self._save()

    def get_sorted_groups(self) -> List[str]:
        """Return group names sorted alphabetically."""
        return sorted(self._data.get(DEFAULT_SECTION, {}).keys())

    def get_ungrouped(self, all_db_names: List[str]) -> List[str]:
        """Return db_names that don't belong to any group."""
        grouped = {
            name
            for members in self._data.get(DEFAULT_SECTION, {}).values()
            for name in members
        }
        return sorted(db for db in all_db_names if db not in grouped)

    def build_display_order(self, all_db_names: List[str]) -> Dict[str, List[str]]:
        """
        Return an ordered dict suitable for display:
          { group_name: [db, ...], ..., "Ungrouped": [...] }
        Groups are sorted; ungrouped items at the end (omitted if empty).
        """
        result: Dict[str, List[str]] = {}
        for group in self.get_sorted_groups():
            members = [
                db for db in self._data[DEFAULT_SECTION].get(group, [])
                if db in all_db_names
            ]
            result[group] = sorted(members)  # include empty groups so they are visible
        ungrouped = self.get_ungrouped(all_db_names)
        if ungrouped:
            result["Ungrouped"] = ungrouped
        return result
