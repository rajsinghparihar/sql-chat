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
