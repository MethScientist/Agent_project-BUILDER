import re
from pathlib import Path
class GranularFileEditor:
    def __init__(self, base_path):
        self.base_path = Path(base_path)

    def _full(self, rel):
        p = (self.base_path / rel).resolve()
        if not str(p).startswith(str(self.base_path)):
            raise ValueError("Path outside project root")
        return p

    def read(self, path):
        p = self._full(path)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write(self, path, content):
        p = self._full(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def insert_after_pattern(self, path, pattern, code):
        text = self.read(path)
        updated = re.sub(pattern, lambda m: m.group(0) + "\n" + code, text, count=1)
        self.write(path, updated)
        return True

    def insert_before_pattern(self, path, pattern, code):
        text = self.read(path)
        updated = re.sub(pattern, code + "\n" + r"\g<0>", text, count=1)
        self.write(path, updated)
        return True

    def insert_in_function(self, path, func_name, code, after_line=None):
        """
        Insert code inside a Python function. If after_line is None, add at start of function body.
        """
        text = self.read(path)
        pattern = re.compile(rf"(def\s+{re.escape(func_name)}\(.*?\):)([\s\S]*?)(?=^def|\Z)", re.MULTILINE)
        match = pattern.search(text)
        if not match:
            raise ValueError(f"Function {func_name} not found in {path}")

        header, body = match.group(1), match.group(2)
        lines = body.splitlines()
        indent = " " * (len(lines[1]) - len(lines[1].lstrip())) if len(lines) > 1 else "    "
        insertion = indent + code.strip().replace("\n", "\n" + indent) + "\n"

        if after_line:
            idx = next((i for i, l in enumerate(lines) if after_line in l), 0) + 1
            lines.insert(idx, insertion.rstrip())
        else:
            lines.insert(1, insertion.rstrip())

        new_body = "\n".join(lines)
        new_text = text[:match.start()] + header + new_body + text[match.end():]
        self.write(path, new_text)
        return True
