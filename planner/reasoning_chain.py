# planner/reasoning_chain.py
# verify : done

from ai_models.gpt_interface import GPTInterface


class ReasoningChain:
    def __init__(self):
        self.gpt = GPTInterface(role="reasoner")


    def reason_through_prompt(self, prompt):
        reasoning_prompt = (
            "Let's break this project prompt down into logical reasoning steps "
            "before writing a plan.\n"
            "Think step by step and explain each subgoal needed to complete it.\n\n"
            f"Prompt: {prompt}"
        )
        thoughts = self.gpt.ask_gpt(reasoning_prompt)
        return thoughts
