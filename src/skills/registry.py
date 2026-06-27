import os
from typing import Dict, Optional

class SkillsRegistry:
    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir is None:
            # Locate relative to src directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.skills_dir = os.path.join(base_dir, "skills")
        else:
            self.skills_dir = skills_dir
        self.skills: Dict[str, str] = {}
        self.load_skills()

    def load_skills(self):
        """Loads all skills (txt or md files) from the skills directory."""
        if not os.path.exists(self.skills_dir):
            return
        for file in os.listdir(self.skills_dir):
            if file.endswith(".txt") or file.endswith(".md"):
                name = os.path.splitext(file)[0]
                try:
                    with open(os.path.join(self.skills_dir, file), "r", encoding="utf-8") as f:
                        self.skills[name] = f.read().strip()
                except Exception:
                    pass

    def get_skill(self, name: str) -> Optional[str]:
        """Gets a skill by name."""
        return self.skills.get(name)

# Global registry instance
skills_registry = SkillsRegistry()
