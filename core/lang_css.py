# core/lang_css.py
import re
from typing import List


# extract classes like .my-class, .foo_bar
CLASS_RE = re.compile(r"\.([A-Za-z0-9_-]+)\b")

def extract_css_class_names(source: str) -> List[str]:
    return sorted(set(CLASS_RE.findall(source)))
