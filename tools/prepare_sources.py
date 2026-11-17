"""Reassemble the versioned source assets and verify every SHA-256 checksum."""

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_sources(source_dir: Path) -> dict:
    manifest = json.loads((source_dir / "manifest.json").read_text("utf-8"))
    for name, info in manifest["files"].items():
        target = source_dir / name
        if target.exists() and sha256_file(target) == info["sha256"]:
            continue
        temporary = target.with_name(target.name + ".tmp")
        whole = hashlib.sha256()
        with temporary.open("wb") as output:
            for part in info["parts"]:
                data = (source_dir / part["path"]).read_bytes()
                if (
                    len(data) != part["size"]
                    or hashlib.sha256(data).hexdigest() != part["sha256"]
                ):
                    raise ValueError(f"Damaged source part: {part['path']}")
                whole.update(data)
                output.write(data)
        if (
            temporary.stat().st_size != info["size"]
            or whole.hexdigest() != info["sha256"]
        ):
            raise ValueError(f"Damaged source file: {name}")
        temporary.replace(target)
    return manifest


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    prepare_sources(root / "assets" / "source")
    print("Source assets verified and ready.")
