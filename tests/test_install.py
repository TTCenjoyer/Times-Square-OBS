import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from install import install, merge_existing, render_template


class InstallerTests(unittest.TestCase):
    def test_template_is_portable_and_has_no_personal_capture_devices(self):
        data = render_template(ROOT, Path("atlas.mkv").resolve())
        self.assertEqual(data["resolution"], {"x": 1920, "y": 1080})
        self.assertNotIn("${ROOT}", json.dumps(data))
        self.assertFalse(
            any(
                s["id"] in {"dshow_input", "wasapi_input_capture", "monitor_capture"}
                for s in data["sources"]
            )
        )

    def test_update_preserves_transition_scripts_rules_and_camera(self):
        existing = render_template(ROOT, Path("old.mkv").resolve())
        external = {"path": "other-transitions.lua", "settings": {"duration": 1500}}
        existing["modules"]["scripts-tool"].append(external)
        existing["transitions"] = [
            {"id": "move_transition", "name": "Move", "settings": {"duration": 1500}}
        ]
        camera = {
            "name": "My camera",
            "id": "dshow_input",
            "settings": {"device_id": "keep-this-device"},
        }
        existing["sources"].append(camera)
        before = copy.deepcopy(existing)
        updated = merge_existing(existing, ROOT, Path("new.mkv").resolve())
        self.assertEqual(existing, before)
        self.assertEqual(updated["modules"]["scripts-tool"][1], external)
        self.assertEqual(updated["transitions"], existing["transitions"])
        self.assertEqual(updated["sources"][-1], camera)
        for original, modified in zip(existing["sources"], updated["sources"]):
            if original["id"] == "scene":
                self.assertEqual(original, modified)

    def test_existing_collection_is_backed_up_and_profile_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "obs"
            atlas = Path(temp) / "atlas.mkv"
            atlas.write_bytes(b"fixture")
            destination = install(config, ROOT, atlas)
            original = destination.read_bytes()
            profile = config / "basic/profiles/Times_Square_LIVE/basic.ini"
            profile.write_text(
                "[Video]\nBaseCX=1920\nBaseCY=1080\nCustomSetting=keep\n"
            )
            profile_original = profile.read_bytes()
            with self.assertRaises(FileExistsError):
                install(config, ROOT, atlas)
            install(config, ROOT, atlas, update_existing=True)
            backups = list((config / ".obs-backups").glob("*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertEqual(profile.read_bytes(), profile_original)


if __name__ == "__main__":
    unittest.main()
