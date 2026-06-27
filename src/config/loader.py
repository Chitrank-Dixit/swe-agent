import os
import json

class DevCoachConfig:
    def __init__(self):
        self.base_url = "http://127.0.0.1:1234/v1"
        self.timeout = 600.0
        self.default_model = "qwen/qwen3.5-9b"
        self.judge_model = "qwen/qwen3.5-9b"
        self.default_mode = "plan"
        self.default_workflow = "auto"
        self.database_url = "sqlite:///./coach.db"
        self.log_level = "INFO"
        self.log_file_path = "coach_workflow.log"
        self.agents_rules = ""

        # Load from devcoach.json
        self.load_config()
        # Load from AGENTS.md
        self.load_agents_rules()

    def load_config(self):
        config_path = os.path.join(os.getcwd(), "devcoach.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    provider = data.get("provider", {})
                    lmstudio = provider.get("lmstudio", {})
                    self.base_url = lmstudio.get("baseURL", self.base_url)
                    self.timeout = float(lmstudio.get("timeout", self.timeout))
                    
                    models = lmstudio.get("models", {})
                    self.default_model = models.get("default", self.default_model)
                    self.judge_model = models.get("judge", self.judge_model)
                    
                    defaults = data.get("defaults", {})
                    self.default_mode = defaults.get("mode", self.default_mode)
                    self.default_workflow = defaults.get("workflow", self.default_workflow)
            except Exception as e:
                pass

        # If running inside docker, default localhost/127.0.0.1 to host.docker.internal
        is_docker = os.path.exists('/.dockerenv') or os.path.exists('/proc/self/cgroup')
        if is_docker:
            if "localhost" in self.base_url:
                self.base_url = self.base_url.replace("localhost", "host.docker.internal")
            if "127.0.0.1" in self.base_url:
                self.base_url = self.base_url.replace("127.0.0.1", "host.docker.internal")

        # Also support loading from env vars
        self.database_url = os.getenv("DATABASE_URL", self.database_url)
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.log_file_path = os.getenv("LOG_FILE_PATH", self.log_file_path)
        
        env_timeout = os.getenv("LM_STUDIO_TIMEOUT")
        if env_timeout:
            try:
                self.timeout = float(env_timeout)
            except ValueError:
                pass

    def load_agents_rules(self):
        agents_md_path = os.path.join(os.getcwd(), "AGENTS.md")
        if os.path.exists(agents_md_path):
            try:
                with open(agents_md_path, "r", encoding="utf-8") as f:
                    self.agents_rules = f.read().strip()
            except Exception:
                pass

config = DevCoachConfig()
