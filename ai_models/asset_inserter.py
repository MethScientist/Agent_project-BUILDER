# ai_models/asset_inserter.py

import os
from utils.logger import log_info
from executor.file_creator import FileCreator

class AssetInserter:
    def __init__(self):
        self.creator = FileCreator()
        self.assets_path = "UnityGame/Assets/AI_Assets"

    def insert_placeholder_asset(self, asset_name: str, asset_type: str = "model"):
        file_ext = "fbx" if asset_type == "model" else "anim"
        file_name = f"{asset_name.replace(' ', '_')}.{file_ext}"
        asset_path = os.path.join(self.assets_path, file_name)
        content = f"// Placeholder for {asset_type} '{asset_name}'"

        full_path = self.creator.create_file(asset_path, content)
        log_info(f"🎨 Placeholder {asset_type} added: {file_name}")
