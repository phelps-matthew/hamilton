"""Computes total lines of python code in this repo. For curiousity sake."""

from pathlib import Path


def item_line_count(path):
    path = Path(path)
    if path.is_dir():
        return dir_line_count(path)
    elif path.is_file() and path.suffix == ".py":
        return len(path.read_text().splitlines())
    else:
        return 0


def dir_line_count(dir_path):
    dir_path = Path(dir_path)
    return sum(item_line_count(dir_path / item) for item in dir_path.iterdir())


path = Path("~/dev/hamilton/hamilton").expanduser()
print(dir_line_count(path))
