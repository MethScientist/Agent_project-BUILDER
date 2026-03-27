# planner/creative_enhancer.py 

# verify : done

from utils.searcher import common_patterns_db
from utils.logger import log_info



class CreativeEnhancer:
    def __init__(self):
        self.patterns = common_patterns_db()

    def enhance_prompt(self, user_prompt: str):
        log_info("✨ Enhancing prompt with inferred and creative features...")
        prompt = user_prompt.lower()
        inferred = []
        creative = []

        for p in self.patterns:
            if p["trigger"] in prompt:
                inferred += p["standard_features"]
                creative += p["creative_addons"]

        return {
            "original": user_prompt,
            "inferred_features": list(set(inferred)),
            "creative_addons": list(set(creative))
        }
