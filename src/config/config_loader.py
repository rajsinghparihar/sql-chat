# context_loader.py
from src.config.config_creator import ConfigCreator


class ConfigLoader:
    config_obj = None

    def __init__(self):
        self.config_obj = ConfigCreator().get_config()

    def load_llm_config(self):
        # Load LLM configuration from a file or other source
        llm_params = self.config_obj["llm_params"]
        return llm_params

    def load_path_config(self):
        # Load database configuration like data paths and index storage paths
        paths = self.config_obj["paths"]
        return paths

    def load_prompt_config(self):
        # Load application-specific like different prompt templates
        prompt_templates = self.config_obj["prompt_templates"]
        return prompt_templates

    def load_questions_config(self):
        # Load template questions and approaches
        template_questions = self.config_obj["template_questions"]
        return template_questions
