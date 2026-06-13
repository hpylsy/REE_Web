from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_LIBRARY_ROOT = Path("RandomSpectrum_av2/Pt2")
SAMPLE_FILE_SUFFIXES = {".asc", ".csv", ".txt", ".tsv"}


def list_sample_files(base_dir=None, max_items=120):
    base_path = Path(base_dir).resolve() if base_dir is not None else ROOT_DIR
    absolute_root = base_path / SAMPLE_LIBRARY_ROOT
    samples = []
    seen = set()

    def add_sample(path):
        relative_path = path.relative_to(base_path)
        if relative_path in seen:
            return False
        seen.add(relative_path)
        samples.append(
            {
                "path": str(relative_path),
                "name": path.name,
                "size": path.stat().st_size,
            }
        )
        return True

    if not absolute_root.exists():
        return samples

    for path in sorted(absolute_root.glob("*")):
        if path.suffix.lower() in SAMPLE_FILE_SUFFIXES and path.is_file():
            add_sample(path)
            if len(samples) >= max_items:
                return samples
    return samples
