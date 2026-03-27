# core/lang_cs.py
import re
from typing import List, Optional, Dict


def extract_cs_namespace(source: str) -> Optional[str]:
    m = re.search(r"namespace\s+([A-Za-z0-9_.]+)", source)
    return m.group(1) if m else None

def extract_cs_public_types(source: str) -> List[str]:
    return sorted(set(re.findall(r"\bpublic\s+(?:class|struct|interface)\s+([A-Za-z_]\w*)", source)))

# Combine to map types -> namespace
def cs_exports(source: str) -> Dict[str, str]:
    ns = extract_cs_namespace(source)
    types = extract_cs_public_types(source)
    if ns:
        return {t: ns for t in types}
    return {}
