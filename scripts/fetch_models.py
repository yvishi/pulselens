"""Download the server-side model files into models/ (gitignored). Owned by Ganeev; ported from the old repo.

Default: the MediaPipe face landmarker (a few MB), which the analysis needs for face regions and yaw.
--heavy: also insightface buffalo_l (~280 MB, research licence; only for the optional ArcFace turn.identity, G10).

Not fetched here: the SBI weights (models/sbi/FFc23.tar, G7) sit behind a Google Drive link in the
mapooon/SelfBlendedImages README and are downloaded by hand. Web models are Yash's (scripts/fetch_web_models.py).

A failed download is reported and skipped (setup must work offline); pass --strict to fail instead.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

MP = "https://storage.googleapis.com/mediapipe-models"
LIGHT = {
    "mediapipe/face_landmarker.task": f"{MP}/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
}
HEAVY = {
    "insightface/buffalo_l.zip": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
}


def fetch(rel: str, url: str) -> bool:
    dest = MODELS / rel
    if dest.exists() or (dest.suffix == ".zip" and dest.with_suffix("").exists()):
        print(f"  ok    {rel} (already present)")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
        tmp.replace(dest)
    except Exception as e:  # network errors of every kind are reported, not raised
        tmp.unlink(missing_ok=True)
        print(f"  FAIL  {rel}: {e}")
        return False
    if dest.suffix == ".zip":
        with zipfile.ZipFile(dest) as z:
            z.extractall(dest.with_suffix(""))
        dest.unlink()
    print(f"  got   {rel}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--heavy", action="store_true", help="also fetch insightface buffalo_l")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if any download fails")
    args = ap.parse_args()

    wanted = {**LIGHT, **(HEAVY if args.heavy else {})}
    print(f"Fetching {len(wanted)} model file(s) into {MODELS}")
    failed = [rel for rel, url in wanted.items() if not fetch(rel, url)]
    if failed:
        print(f"{len(failed)} download(s) failed: {', '.join(failed)}. Re-run `python scripts/fetch_models.py` online.")
        if args.strict:
            sys.exit(1)
    sbi = MODELS / "sbi" / "FFc23.tar"
    print(f"  {'ok   ' if sbi.exists() else 'note '} {sbi.relative_to(ROOT)}"
          f"{'' if sbi.exists() else ' is missing: download it by hand for visual.sbi (G7)'}")


if __name__ == "__main__":
    main()
