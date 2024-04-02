import pathlib
from pathlib import Path

PIPE = "│"
ELBOW = "└──"
TEE = "├──"
PIPE_PREFIX = "│   "
SPACE_PREFIX = "    "


class _TreeGenerator:
    def __init__(self, root_dir):
        self._root_dir = pathlib.Path(root_dir).name  # Use directory name
        self._root_path = pathlib.Path(root_dir)
        self._tree = []
        self._depth = 0  # Track the current depth

    def build_tree(self):
        self._tree_head()
        self._tree_body(self._root_path)
        return self._tree

    def _tree_head(self):
        self._tree.append(f"{self._root_dir}/\n")
        self._tree.append(PIPE + "\n")

    def _tree_body(self, directory, prefix=""):
        entries = [e for e in directory.iterdir() if e.name not in ["__pycache__", "__init__.py"]]
        entries = sorted(entries, key=lambda entry: (entry.is_file(), entry.name))
        entries_count = len(entries)
        for index, entry in enumerate(entries):
            connector = ELBOW if index == entries_count - 1 else TEE
            if entry.is_dir():
                self._add_directory(entry, index, entries_count, prefix, connector)
            else:
                self._add_file(entry, prefix, connector)
            if self._depth == 1 and index == entries_count - 1:  # Add space after the last depth=0 directory
                self._tree.append(PIPE + "\n")


    def _add_directory(self, directory, index, entries_count, prefix, connector):
        self._depth += 1
        self._tree.append(f"{prefix}{connector} {directory.name}/\n")
        new_prefix = PIPE_PREFIX if index != entries_count - 1 else SPACE_PREFIX
        self._tree_body(directory=directory, prefix=prefix + new_prefix)
        self._depth -= 1

    def _add_file(self, file, prefix, connector):
        self._tree.append(f"{prefix}{connector} {file.name}\n")


class DirectoryTree:
    def __init__(self, root_dir, output_path):
        self._generator = _TreeGenerator(root_dir)
        self._output_path = output_path

    def generate(self):
        tree = self._generator.build_tree()
        with self._output_path.open("w") as file:
            for entry in tree:
                file.write(entry)


if __name__ == "__main__":
    root_dir = Path(__file__).parent.parent
    output_path = root_dir / "docs" / "repo_tree.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the docs directory exists
    tree = DirectoryTree(root_dir, output_path)
    tree.generate()
