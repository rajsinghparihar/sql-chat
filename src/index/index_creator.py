from sqlalchemy import create_engine, MetaData
from glob import glob
from llama_index import (
    SQLDatabase,
    VectorStoreIndex,
)
from llama_index.indices.struct_store import SQLTableRetrieverQueryEngine
from llama_index.objects import (
    SQLTableNodeMapping,
    ObjectIndex,
    SQLTableSchema,
)
from src.config.config_loader import ConfigLoader
import faiss
from transformers import AutoTokenizer, AutoModel
import json
import torch


class IndexCreator:
    def __init__(self):
        paths = ConfigLoader().load_path_config()
        self._database_dir = paths["database_directory"]

    def build_database_schema(self):
        file_name = glob(pathname=str(self._database_dir) + "/*.db")[0]
        engine = create_engine("sqlite:///" + file_name)

        self._metadata = MetaData()
        self._metadata.reflect(engine)
        self._sql_database = SQLDatabase(engine=engine)

    def build_object_index(self):
        table_node_mapping = SQLTableNodeMapping(sql_database=self._sql_database)
        table_schema_objects = []
        for table_name in self._metadata.tables.keys():
            table_schema_objects.append(SQLTableSchema(table_name=table_name))

        self._object_index = ObjectIndex.from_objects(
            table_schema_objects,
            table_node_mapping,
            VectorStoreIndex,
        )

    def create_query_engine(self):
        self.build_database_schema()
        self.build_object_index()
        query_engine = SQLTableRetrieverQueryEngine(
            self._sql_database,
            self._object_index.as_retriever(similarity_top_k=3, verbose=False),
            sql_only=True,
            synthesize_response=False,
        )

        return query_engine


class FAISSIndex:
    def __init__(self):
        config_loader = ConfigLoader()
        paths = config_loader.load_path_config()
        embedding_model_path = paths["embedding_model_path"]
        embedding_tokenizer_path = paths["embedding_model_path"]
        sql_queries_path = paths["pre_defined_sql_queries_path"]
        self.tokenizer = AutoTokenizer.from_pretrained(embedding_tokenizer_path)
        self.embed_model = AutoModel.from_pretrained(embedding_model_path)

        with open(sql_queries_path, mode="rb") as file:
            content = file.read()
            sql_queries_json_list = json.loads(content)
            self.sql_queries_list = []
            for sql_query_json in sql_queries_json_list:
                sql_query = sql_query_json.get("query", "")
                self.sql_queries_list.append(sql_query)
        self.build_faiss_index()

    def build_faiss_index(self):
        # Tokenize and obtain embeddings
        inputs = self.tokenizer(
            self.sql_queries_list, return_tensors="pt", padding=True, truncation=True
        )
        with torch.no_grad():
            outputs = self.embed_model(**inputs)

        # Extract embeddings from the last layer
        sentence_embeddings = outputs.last_hidden_state.mean(dim=1).numpy()

        # Assuming vectors from the model with a specific dimensionality
        d = sentence_embeddings.shape[1]

        # Create FAISS index
        self.index = faiss.IndexFlatL2(d)
        self.index.add(sentence_embeddings)

    def match_question(self, question):
        # data specific string handling
        question = question.replace("product", "zposdesc").replace("item", "zposdesc")
        question = question.replace("category", "level3_desc")
        question = (
            question.replace("distributor", "DC")
            .replace("distribution center", "DC")
            .replace("supplier", "DC")
        )
        # Tokenize and obtain embedding for the query
        query_input = self.tokenizer(
            question, return_tensors="pt", padding=True, truncation=True
        )
        with torch.no_grad():
            query_output = self.embed_model(**query_input)

        # Extract embedding from the last layer
        query_embedding = query_output.last_hidden_state.mean(dim=1).numpy()

        # Perform similarity search
        distances, indices = self.index.search(query_embedding, k=1)
        return self.sql_queries_list[indices[0][0]]
