# api.py
from src.index.index_creator import IndexCreator, FAISSIndex
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

    def get_llm_response(
        self, user_question, result, summarize: Optional[bool] = False
    ):
        if summarize:
            prompt = self._prompt_templates["summary_template"].format(
                schema_str=self._schema_str, result=result
            )
        else:
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
        sql_query = str(response.metadata["sql_query"]).split("sql")[-1].split(";")[0]

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
                    str(response.metadata["sql_query"]).split("sql")[-1].split(";")[0]
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

        result = result.tail(10)  # works even if result had < 10 rows
        result = self._database_utils_instance.format_numeric_columns(result)
        result_dict = result.to_dict(orient="records")
        result_sample = result.to_json(orient="split")

        string_response = self.get_llm_response(
            user_question=user_question, result=result_sample, summarize=True
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
        sql_query = str(metadata["sql_query"]).split("sql")[-1].split(";")[0]
        print(sql_query)

        return sql_query

    def get_user_question_response_fast(self, user_question, evidence=""):
        sql_query = self.get_sql_query_fast(
            user_question=user_question,
            evidence=evidence,
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

        result = result.tail(10)  # works even if result had < 10 rows
        result = self._database_utils_instance.format_numeric_columns(result)
        result_dict = result.to_dict(orient="records")
        result_sample = result.to_json(orient="split")

        string_response = self.get_llm_response(
            user_question=user_question, result=result_sample, summarize=True
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

            result = response.get("result", [])[1].get("output_data")
            description = response.get("result", [])[0].get("output_data")
            present_format = "tile" if len(result) == 1 else "table"

            if len(result) > 0:
                columns = list(result[0].keys())
                column_names = [col.replace("_", " ").upper() for col in columns]
                result_dict = (
                    result[0]
                    if len(result) == 1
                    else {
                        "data": result,
                        "columns": columns,
                        "column_names": column_names,
                    }
                )
            else:
                result_dict = {"data": [], "columns": [], "column_names": []}

            insight_response = {
                "question": question,
                "result": result_dict,
                "output_format": "json",
                "present_format": present_format,
                "description": description,
            }
            response_list.append(insight_response)
        response_dict = {"insights": response_list}
        return response_dict


class NonLLMAPI(BaseAPI, FAISSIndex):
    def __init__(self):
        BaseAPI.__init__(self)
        FAISSIndex.__init__(self)

    def get_user_question_response(self, user_question):
        sql_query = self.match_question(user_question)
        result = self.get_sql_result(sql_query)
        result_dict = result.to_dict(orient="records")
        result = result.head(10)  # works even if result had < 10 rows

        response = self.get_llm_response(
            user_question=user_question, result=result, summarize=True
        )
        final_response = {
            "result": [
                {
                    "output_type": "string",
                    "output_data": response,
                },
                {"output_type": "json", "output_data": result_dict},
            ]
        }
        return final_response


class SummaryAPI(FastBaseAPI, NonLLMAPI):
    def __init__(self):
        FastBaseAPI.__init__(self)
        NonLLMAPI.__init__(self)
        self.template_keywords = [
            "brands",
            "brand",
            "distributor",
            "DC",
            "DCs",
            "distribution",
            "center",
            "distributors",
            "products",
            "items",
            "SKU",
            "monthly",
            "yearly",
        ]

    def get_summary_questions(self, keywords):
        questions_generation_template = self._prompt_templates[
            "summary_questions_generation_template"
        ]
        prompt = questions_generation_template.format(
            schema_str=self._schema_str, keywords=keywords
        )

        response = self._llm.complete(prompt)
        print(response.text)
        response = json.loads(response.text)
        return response

    def get_summary(self, user_input):
        response_list = []
        keywords = user_input.split()
        filtered_keywords = []
        for keyword in keywords:
            if keyword in self.template_keywords:
                filtered_keywords.append(keyword)

        # no template found for keyword i.e. new keyword -> generate sql
        if filtered_keywords == []:
            questions = self.get_summary_questions(keywords=keywords)
            for question in questions.values():
                response = self.get_user_question_response_fast(user_question=question)
                response_list.append(response)
        else:
            for keyword in filtered_keywords:
                response = self.get_user_question_response(user_question=keyword)
                response_list.append(response)

        return {"result": response_list}


class TemplateBasedQAAPI(BaseAPI):
    def __init__(self):
        super().__init__()
        config_loader = ConfigLoader()
        self._database_utils_instance = DatabaseUtils()
        self._paths = config_loader.load_path_config()
        template_sql_config_filepath = self._paths[
            "pre_defined_qna_template_sql_queries_path"
        ]
        with open(template_sql_config_filepath, mode="rb") as file:
            content = file.read()
            qna_config = json.loads(content)
            self.sql_query_templates_map = qna_config.get("sql_queries")
            self.time_period_map = qna_config.get("time_period_map")
            self.position_map = qna_config.get("position_map")
            self.sales_type_map = qna_config.get("sales_type_map")
            self.state_codes_map = qna_config.get("state_code_map")
            self.time_frame_map = qna_config.get("time_frame_map")

    def get_user_question_response(
        self, user_inputs: dict, question_num: int, fast: Optional[bool] = False
    ):
        period = user_inputs.get("period", "")
        position = user_inputs.get("position", "")
        sales_type = user_inputs.get("sale_type", "")
        product_name = user_inputs.get("sku", "")
        time_frame = user_inputs.get("time_frame", "")
        state_name = user_inputs.get("state", "")
        start_date = user_inputs.get("from", "")
        end_date = user_inputs.get("to", "")

        if question_num == 1:
            template = self.sql_query_templates_map["avg_sales_template_sql"]
        elif question_num == 2:
            template = self.sql_query_templates_map["total_sales_template_sql"]
        elif question_num == 3:
            template = self.sql_query_templates_map["growth_rate_template_sql"]
        else:
            template = self.sql_query_templates_map["top_products_template_sql"]

        sql_query = template.format(
            quantity_or_value=self.sales_type_map.get(sales_type, ""),
            time_period=self.time_period_map.get(period, ""),
            product_name=product_name,
            state_code=self.state_codes_map.get(state_name, ""),
            time_frame=self.time_period_map.get(
                self.time_frame_map.get(time_frame, "")
            ),
            start_date=start_date,
            end_date=end_date,
            position=self.position_map.get(position, ""),
        )

        result = self._database_utils_instance.run_sql_query(sql_query=sql_query)

        if result.__contains__("sqlite_error"):
            log_msg = f"user_question: {user_inputs} - sql_query: {sql_query} - error: {result}"
            self.logger_instance.error(log_msg)
            return {
                "result": [
                    {"output_type": "string", "output_data": "Could not process query."}
                ]
            }

        result_data = result.to_dict(orient="records")
        result = result.head(10)
        result_sample = result.to_json(orient="values")
        result_text = (
            f"Here are the results: \n{result.to_string(index=False)}"
            if fast
            else self.get_llm_response(
                user_question="", result=result_sample, summarize=True
            )
        )
        final_response = {
            "result": [
                {
                    "output_type": "string",
                    "output_data": result_text,
                },
                {"output_type": "json", "output_data": result_data},
            ]
        }
        return final_response
