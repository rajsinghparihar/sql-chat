# api.py
from src.index.index_creator import IndexCreator
from src.config.config_loader import ConfigLoader
from src.utils.utils import DatabaseUtils, Logger
from llama_index.schema import QueryBundle
import json
from typing import Optional


class BaseAPI:
    def __init__(self):
        self._prompt_templates = ConfigLoader().load_prompt_config()
        self._query_engine = IndexCreator().create_query_engine()
        self._llm = self._query_engine.service_context.llm
        self._database_utils_instance = DatabaseUtils()
        self._schema_str = self._database_utils_instance.get_schema_str()
        self._fk_str = self._database_utils_instance.get_fk_str()
        self.max_tries = 2
        self.logger_instance = Logger()

    def get_llm_response(self, user_question, result):
        prompt = self._prompt_templates["human_like_response_template"].format(
            user_question=user_question, result=result
        )
        response = self._llm.complete(prompt)
        return str(response)

    def get_sql_query(self, user_question, evidence=""):
        prompt = self._prompt_templates["decomposer_template"].format(
            schema_str=self._schema_str,
            fk_str=self._fk_str,
            query=user_question,
            evidence=evidence,
        )
        response = self._query_engine.query(prompt)

        # string splitted by the substring 'sql' and take the last element,
        # split again on extra back-ticks and take the substring, left of the ```
        # intuition behind taking the last element: since decomposer outputs sql in sub-questions,
        # usually the sql code of the last sub-question is the complete sql code that solves the original question.
        sql_query = str(response.metadata["sql_query"]).split("sql")[-1].split("```")[0]

        return sql_query

    def get_sql_result(self, sql_query):
        return self._database_utils_instance.run_sql_query(sql_query=sql_query)

    def get_user_question_response(self, user_question, evidence=""):
        result = None
        sql_query = self.get_sql_query(user_question=user_question, evidence=evidence)
        for _ in range(self.max_tries):
            result = self.get_sql_result(sql_query=sql_query)
            if result.__contains__("sqlite_error"):
                sqlite_error = result.get("sqlite_error")
                exception_class = result.get("exception_class")

                prompt = self._prompt_templates["refiner_template"].format(
                    query=user_question,
                    evidence=evidence,
                    schema_str=self._schema_str,
                    fk_str=self._fk_str,
                    sql=sql_query,
                    sqlite_error=sqlite_error,
                    exception_class=exception_class,
                )
                response = self._query_engine.query(prompt)
                sql_query = (
                    str(response.metadata["sql_query"]).split("sql")[-1].split("```")[0]
                )
            else:
                break

        if result.__contains__("sqlite_error"):
            log_msg = f"user_question: {user_question} - sql_query: {sql_query} - error: {result}"
            self.logger_instance.error(log_msg)
            return {
                "result": [
                    {"output_type": "string", "output_data": "Could not process query."}
                ]
            }

        result_dict = result.to_dict(orient="records")
        result = result.head(10)  # works even if result had < 10 rows
        result_sample = result.to_json(orient="values")

        string_response = self.get_llm_response(
            user_question=user_question, result=result_sample
        )

        final_response = {
            "result": [
                {
                    "output_type": "string",
                    "output_data": string_response,
                },
                {"output_type": "json", "output_data": result_dict},
            ]
        }

        log_msg = f"user_question: {user_question} - sql_query: {sql_query} - response: {final_response}"
        self.logger_instance.success(log_msg)

        return final_response


class FastBaseAPI(BaseAPI):
    def __init__(self):
        super().__init__()

    def get_sql_query_fast(self, user_question, evidence=""):
        prompt = self._prompt_templates["detail_template"].format(
            schema_str=self._schema_str,
            fk_str=self._fk_str,
            query=user_question,
            evidence=evidence,
        )
        query_bundle = QueryBundle(prompt)
        _, metadata = self._query_engine._sql_retriever.retrieve_with_metadata(
            query_bundle
        )
        sql_query = str(metadata["sql_query"]).split("sql")[-1].split("```")[0]

        return sql_query

    def get_user_question_response_fast(self, user_question, evidence=""):
        sql_query = self.get_sql_query_fast(
            user_question=user_question, evidence=evidence
        )
        result = self.get_sql_result(sql_query=sql_query)

        if result.__contains__("sqlite_error"):
            log_msg = f"user_question: {user_question} - sql_query: {sql_query} - error: {result}"
            self.logger_instance.error(log_msg)
            return {
                "result": [
                    {"output_type": "string", "output_data": "Could not process query."}
                ]
            }

        result_dict = result.to_dict(orient="records")
        result = result.head(10)  # works even if result had < 10 rows
        result_sample = result.to_json(orient="values")

        string_response = self.get_llm_response(
            user_question=user_question, result=result_sample
        )

        final_response = {
            "result": [
                {
                    "output_type": "string",
                    "output_data": string_response,
                },
                {"output_type": "json", "output_data": result_dict},
            ]
        }

        log_msg = f"user_question: {user_question} - sql_query: {sql_query} - response: {final_response}"
        self.logger_instance.success(log_msg)

        return final_response


class InsightsAPI(FastBaseAPI):
    def __init__(
        self,
        n_ques: Optional[int] = 3,
        automatic: Optional[bool] = False,
        fast: Optional[bool] = True,
    ):
        super().__init__()
        self.automatic = automatic
        self.n_ques = n_ques
        self.fast = fast
        if not self.automatic:
            self._template_questions = ConfigLoader().load_questions_config()

    def generate_insight_questions(self):
        prompt = self._prompt_templates["insights_question_generation_template"].format(
            n_ques=self.n_ques, schema_str=self._schema_str, fk_str=self._fk_str
        )
        response = self._llm.complete(prompt)
        return response

    def get_insight_questions(self):
        if self.automatic:
            response = self.generate_insight_questions()
        else:
            response = self._template_questions["questions_approaches"]
        json_response = json.loads(str(response))
        questions = json_response.get("response", {}).get("questions", {})
        approaches = json_response.get("response", {}).get("approach", {})

        return questions, approaches

    def get_insights(self):
        response_list = []
        questions, approaches = self.get_insight_questions()
        for question, approach in zip(questions.values(), approaches.values()):
            if self.fast:
                response = self.get_user_question_response_fast(
                    user_question=question, evidence=approach
                )
            else:
                response = self.get_user_question_response(
                    user_question=question, evidence=approach
                )
            response_list.append(response)
        response_dict = {"result": response_list}
        return response_dict
