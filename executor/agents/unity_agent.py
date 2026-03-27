# executor/agents/unity_agent.py

from ai_models.unity_generator import UnityGenerator
from utils.logger import log_info


class UnityAgent:
    def __init__(self, context_manager=None):
        self.context_manager = context_manager
        self.generator = UnityGenerator(context_manager=context_manager)

    def execute_step(self, step):
        if self.context_manager and hasattr(self.context_manager, "record"):
            self.context_manager.record("unity_step", step)
        description = step.get("description", "").lower()
        try:
            if "player" in description:
                self.generator.generate_player_controller()
            elif "camera" in description:
                self.generator.generate_camera_follow()
            elif "game manager" in description or "manager" in description:
                self.generator.generate_game_manager()
            else:
                self.generator.generate_script(
                    description.replace(" ", ""), logic="// Unity logic here"
                )

            log_info(f"🎮 Unity step executed: {description}")
            return {"status": "success", "step": step}

        except Exception as e:
            log_info(f"❌ Unity agent failed: {e}")
            return {"status": "fail", "step": step, "error": str(e)}
