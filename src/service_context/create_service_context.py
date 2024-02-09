# create_service_context.py
from src.utils.llm_loader import LLMLoader
from llama_index import ServiceContext, set_global_tokenizer, set_global_service_context
from llama_index.embeddings import HuggingFaceEmbedding
from src.config.config_loader import ConfigLoader
from transformers import AutoTokenizer


class ServiceContextCreator:
    def __init__(self):
        self.llm_loader = LLMLoader()
        paths = ConfigLoader().load_path_config()
        embedding_model_path = paths["embedding_model_path"]
        tokenizer_path = paths["tokenizer_path"]
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.embed_model = HuggingFaceEmbedding(embedding_model_path)

    def create_service_context(self):
        # Logic to create service context using the loaded LLM instance
        llm_instance = self.llm_loader.get_llm_instance()
        service_context = ServiceContext.from_defaults(
            llm=llm_instance, embed_model=self.embed_model
        )
        return service_context

    def set_service_context(self):
        service_context = self.create_service_context()
        set_global_service_context(service_context=service_context)
        set_global_tokenizer(self.tokenizer.encode)
