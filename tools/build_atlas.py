"""Build the synchronized, lossless background/mask/UV video used by OBS."""

import argparse
import gzip
import json
import subprocess
import time
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

from mesh_mapping import H, W, fill_uv
from prepare_sources import prepare_sources

ROOT = Path(__file__).resolve().parents[1]


def build(
    source: Path, output: Path, start: int = 0, frames: int | None = None
) -> dict:
    manifest = prepare_sources(source)
    with gzip.open(source / "tracking.json.gz", "rt", encoding="utf-8-sig") as stream:
        tracking = json.load(stream)
    stop = len(tracking["frames"]) if frames is None else start + frames
    if not 0 <= start < stop <= len(tracking["frames"]):
        raise ValueError("Requested frame range is outside the source clip")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + ".part.mkv")
    base = cv2.VideoCapture(str(source / "base.mp4"))
    matte = cv2.VideoCapture(str(source / "matte.mov"))
    for capture in (base, matte):
        if not capture.isOpened():
            raise ValueError("Cannot open source video")
        if (
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        ) != (W, H):
            raise ValueError("Source resolution must be 1080 x 1920")
    if start:
        base.set(cv2.CAP_PROP_POS_FRAMES, start)
        matte.set(cv2.CAP_PROP_POS_FRAMES, start)
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{W * 3}x{H}",
        "-r",
        str(manifest["fps"]),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "utvideo",
        "-pix_fmt",
        "gbrp",
        "-pred",
        "median",
        "-threads",
        "4",
        str(temporary),
    ]
    began = time.monotonic()
    completed = 0
    folded = 0
    log_path = output.with_suffix(".log")
    with log_path.open("w", encoding="utf-8") as log:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            for index in range(start, stop):
                ok_base, background = base.read()
                ok_mask, original_mask = matte.read()
                if not ok_base or not ok_mask:
                    raise ValueError(f"Missing source frame: {index}")
                ids, uv, alpha, checks = fill_uv(
                    tracking["frames"][index], original_mask[:, :, 0]
                )
                if np.any((alpha > 0) & (ids == 0)):
                    raise ValueError(f"Unassigned billboard pixels in frame {index}")
                if checks["folded_triangles_in_frame"]:
                    raise ValueError(f"Folded mesh in frame {index}")
                folded += checks["folded_triangles_in_frame"]
                packed = np.rint(uv * 4095).astype(np.uint16)
                coordinates = np.empty_like(background)
                coordinates[:, :, 2] = packed[:, :, 0] >> 4
                coordinates[:, :, 1] = packed[:, :, 1] >> 4
                coordinates[:, :, 0] = ((packed[:, :, 0] & 15) << 4) | (
                    packed[:, :, 1] & 15
                )
                mask_and_id = np.zeros_like(background)
                mask_and_id[:, :, 2] = alpha
                mask_and_id[:, :, 1] = ids * 16
                encoder.stdin.write(
                    np.concatenate(
                        (background, mask_and_id, coordinates), axis=1
                    ).tobytes()
                )
                completed += 1
                if completed % 30 == 0 or index == stop - 1:
                    print(
                        f"{completed}/{stop - start} frames ({time.monotonic() - began:.1f}s)",
                        flush=True,
                    )
        finally:
            if encoder.stdin:
                encoder.stdin.close()
            return_code = encoder.wait()
            base.release()
            matte.release()
    if return_code or completed != stop - start:
        raise RuntimeError(f"Encoding failed; see {log_path}")
    temporary.replace(output)
    report = {
        "frames": completed,
        "start_frame": start,
        "fps": manifest["fps"],
        "atlas_resolution": [W * 3, H],
        "film_resolution": [W, H],
        "uv_precision_bits": 12,
        "folded_triangles": folded,
        "codec": "UtVideo RGB lossless",
        "elapsed_seconds": round(time.monotonic() - began, 1),
    }
    output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "assets" / "source")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "assets" / "generated" / "times-square-live-v2.mkv",
    )
    parser.add_argument("--start-frame", type=int, default=0, help="Debug builds only")
    parser.add_argument(
        "--frames", type=int, help="Debug builds only; default is the complete clip"
    )
    parser.add_argument(
        "--force", action="store_true", help="Replace an existing generated atlas"
    )
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        parser.error("Output exists; choose another path or pass --force")
    print(
        json.dumps(
            build(
                args.source.resolve(),
                args.output.resolve(),
                args.start_frame,
                args.frames,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
