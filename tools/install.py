"""Install or update the Times Square collection without replacing other OBS settings."""

import argparse
import copy
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = "Times_Square_LIVE.json"


def render_template(root: Path, atlas: Path) -> dict:
    text = (root / "obs" / "scene-collection.template.json").read_text("utf-8")
    data = json.loads(text.replace("${ROOT}", root.as_posix()))
    for source in data["sources"]:
        if any(f["id"] == "times_square_live_v1" for f in source.get("filters", [])):
            source["settings"]["local_file"] = atlas.as_posix()
    return data


def merge_existing(existing: dict, root: Path, atlas: Path) -> dict:
    """Update only this plugin's file paths; preserve cameras, layouts and transitions."""
    data = copy.deepcopy(existing)
    scripts = data.setdefault("modules", {}).setdefault("scripts-tool", [])
    plugin = next(
        (s for s in scripts if Path(s["path"]).name == "times-square-live.lua"), None
    )
    if plugin is None:
        scripts.append(
            {
                "path": (root / "obs" / "times-square-live.lua").as_posix(),
                "settings": {},
            }
        )
    else:
        plugin["path"] = (root / "obs" / "times-square-live.lua").as_posix()
    matched = False
    for source in data.get("sources", []):
        if any(f["id"] == "times_square_live_v1" for f in source.get("filters", [])):
            source["settings"]["local_file"] = atlas.as_posix()
            matched = True
    if not matched:
        raise ValueError(
            "Existing collection has no Times Square filter; refusing to overwrite it"
        )
    return data


def install(
    config: Path, root: Path, atlas: Path, update_existing: bool = False
) -> Path:
    if not atlas.is_file():
        raise FileNotFoundError(f"Build the atlas first: {atlas}")
    destination = config / "basic" / "scenes" / COLLECTION
    if destination.exists():
        if not update_existing:
            raise FileExistsError(
                "Collection exists. Use --update-existing to preserve and update it"
            )
        data = merge_existing(
            json.loads(destination.read_text("utf-8-sig")), root, atlas
        )
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = config / ".obs-backups" / f"Times_Square_LIVE-{stamp}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, backup)
    else:
        data = render_template(root, atlas)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(destination)
    # Create a dedicated profile only when it does not already exist.
    profile = config / "basic" / "profiles" / "Times_Square_LIVE" / "basic.ini"
    if not profile.exists():
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(
            "[General]\nName=Times Square LIVE\n\n[Output]\nMode=Simple\n\n"
            "[Video]\nBaseCX=1920\nBaseCY=1080\nOutputCX=1920\nOutputCY=1080\n"
            "FPSType=0\nFPSCommon=30\nColorFormat=NV12\nColorSpace=709\nColorRange=Partial\n\n"
            "[Audio]\nSampleRate=48000\nChannelSetup=Stereo\n",
            encoding="utf-8",
        )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--obs-config",
        type=Path,
        help="OBS configuration directory; defaults to %%APPDATA%%/obs-studio",
    )
    parser.add_argument(
        "--atlas",
        type=Path,
        default=ROOT / "assets" / "generated" / "times-square-live-v2.mkv",
    )
    parser.add_argument("--update-existing", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("The installer targets OBS Studio on Windows")
    result = subprocess.run(
        ["tasklist", "/fi", "IMAGENAME eq obs64.exe"], capture_output=True, text=True
    )
    if "obs64.exe" in result.stdout.lower():
        parser.error("Close OBS Studio before installing or updating")
    config = args.obs_config or Path(os.environ["APPDATA"]) / "obs-studio"
    print(install(config.resolve(), ROOT, args.atlas.resolve(), args.update_existing))
    print("Open OBS and select the Times Square LIVE profile and scene collection.")


if __name__ == "__main__":
    main()
