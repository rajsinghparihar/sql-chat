# llm_loader.py
from llama_index.llms import LlamaCPP
from llama_index.llms.llama_utils import (
    messages_to_prompt,
    completion_to_prompt,
)
from src.config.config_loader import ConfigLoader


class LLMLoader:
    _instance = None
    _llm_instance = None
    context_loader_instance = ConfigLoader()

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(LLMLoader, cls).__new__(cls)
            cls._llm_instance = cls._load_llm()
        return cls._instance

    @classmethod
    def _load_llm(cls):
        # Logic to load LLM instance from storage to memory
        llm_params = cls.context_loader_instance.load_llm_config()
        llm_instance = LlamaCPP(
            model_path=llm_params["llm_model_file"],
            temperature=int(llm_params["temperature"]),
            max_new_tokens=int(llm_params["max_new_tokens"]),
            context_window=int(llm_params["context_window"]),
            messages_to_prompt=messages_to_prompt,
            completion_to_prompt=completion_to_prompt,
            model_kwargs={
                "n_gpu_layers": int(llm_params["n_gpu_layers"]),
                "repeat-penalty": float(llm_params["repeat_penalty"]),
            },
            verbose=bool(llm_params["verbose_flag"]),
        )

        return llm_instance

    def get_llm_instance(self):
        return self._llm_instance
