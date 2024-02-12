import pandas as pd
from sqlalchemy import text
from src.index.index_creator import IndexCreator
from src.config.config_loader import ConfigLoader


class DatabaseUtils:
    def __init__(self):
        index_creator_instance = IndexCreator()
        index_creator_instance.build_database_schema()  # builds sql_database object with the schema using the database
        self._metadata = index_creator_instance._metadata
        self._engine = index_creator_instance._sql_database.engine

    def run_sql_query(self, sql_query):
        with self._engine.connect() as con:
            try:
                result = pd.read_sql_query(sql_query, con)
                return result
            except Exception as er:
                print(er)
                print("Error: ", " ".join(er.args))
                print("Exception Class: ", str(er.__class__))
                return {
                    "sqlite_error": " ".join(er.args),
                    "exception_class": str(er.__class__),
                }
            finally:
                if con:
                    con.close()

    def get_fk_str(self):
        fk_str = ""
        for table_name, table in self._metadata.tables.items():
            for column in table.columns:
                if column.foreign_keys:
                    foreign_key_info = (
                        column.foreign_keys.pop()
                    )  # Assuming a column has at most one foreign key
                    referenced_table = foreign_key_info.column.table.name
                    fk_str += f"{table_name}.`{column.name}` -> {referenced_table}.`{foreign_key_info.column.name}`\n"
        return fk_str

    def get_column_descriptions(self):
        """
        Logic currently works for column description details for single table data.
        todo: Fix this later.
        """
        paths = ConfigLoader().load_path_config()
        transaction_data_col_desc = pd.read_excel(
            paths["column_descriptions_file_path"], sheet_name="Columns description"
        )
        transaction_data_col_desc = transaction_data_col_desc[
            ["COLUMN NAME", "COLUMN DESCRIPTION"]
        ]
        col_desc_dict_list = transaction_data_col_desc.to_dict(orient="records")

        column_descriptions = {}
        for table_name in list(self._metadata.tables.keys()):
            column_descriptions_dict = {}
            for col_desc_dict in col_desc_dict_list:
                column_name = list(col_desc_dict.values())[0]
                column_description = list(col_desc_dict.values())[1]
                column_descriptions_dict[column_name] = column_description

            column_descriptions[table_name] = column_descriptions_dict

        return column_descriptions

    def get_schema_str(self):
        schema_str = ""
        column_descriptions = self.get_column_descriptions()
        for table_name in self._metadata.tables:
            table_template = """
# Table: {table_name}
[
{table_info}]
"""
            table_info = ""
            for column_name, _ in list(
                self._metadata.tables[table_name].columns.items()
            ):
                column_description = column_descriptions.get(table_name, {}).get(
                    column_name, ""
                )
                column_values = []
                with self._engine.connect() as conn:
                    result = conn.execute(
                        text(f"SELECT {column_name} from {table_name} LIMIT 4")
                    )
                    for row in result:
                        column_values.append(row[0])
                    column_values = str(column_values)
                    conn.close()

                table_info += f"\t({column_name}, {column_description}, Value Examples: {column_values})\n"
            table_template = table_template.format(
                table_name=table_name, table_info=table_info
            )
            schema_str += table_template
            schema_str += "\n"

        return schema_str
    
