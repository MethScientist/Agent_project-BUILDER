from ai_models.gpt_interface import GPTInterface
import os


class LanguageDetector:
    def __init__(self):
        self.gpt = GPTInterface(role="language_detector")

    def detect_language(self, path: str, description: str = "") -> str:
        ext = os.path.splitext(path)[1].lower()
        static_map = {
            ".py": "python",
            ".cs": "c#",
            ".js": "javascript",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".java": "java",
            ".cpp": "cpp",
            ".ts": "typescript",
        }

        if ext in static_map:
            return static_map[ext]

        # Ask GPT if file type is unknown or context is needed
        prompt = (
            f"What is the most appropriate programming language to implement this task:\n"
            f"File: {path}\n"
            f"Description: {description}\n"
            "Respond with just the language name (e.g. Python, C#, JavaScript)."
        )
        result = self.gpt.ask_gpt(prompt)
        return result.strip().lower()
