# config_creator.py
import configparser


class ConfigCreator:
    _config = None

    def __init__(self):
        self._config = self.create_default_config()

    def create_default_config(self):
        # Create a default configuration with default values
        config = configparser.ConfigParser()
        config.add_section("paths")
        config.set("paths", "embedding_model_path", "BAAI/bge-base-en-v1.5")
        config.set(
            "paths", "tokenizer_path", "macadeliccc/laser-dolphin-mixtral-2x7b-dpo"
        )
        config.set("paths", "database_directory", "data/db")
        config.set("paths", "index_storage_directory", "data/storage")
        config.set(
            "paths",
            "column_descriptions_file_path",
            "data/csv/Electronics data dictionary.xlsx",
        )

        config.add_section("llm_params")
        config.set(
            "llm_params",
            "llm_model_file",
            "models/laser-dolphin-mixtral-2x7b-dpo.Q4_K_M.gguf",
        )
        config.set("llm_params", "llm_model_type", "mistral")
        config.set("llm_params", "max_new_tokens", "2048")
        config.set("llm_params", "context_window", "7000")
        config.set("llm_params", "temperature", "0")
        config.set("llm_params", "verbose_flag", "False")
        config.set("llm_params", "n_gpu_layers", "8")
        config.set("llm_params", "repeat_penalty", "1.1")

        # config.add_section('custom_prompts')
        # config.set('custom_prompts', 'llm_context_qa_prompt','return chat')
        # config.set('custom_prompts', 'llm_context_sqa_prompt', 'return sql')
        # config.set('custom_prompts', 'llm_summary_prompt', 'return summary')

        config.add_section("prompt_templates")
        config.set(
            "prompt_templates",
            "human_like_response_template",
            """You are a helpful assistant.
Your sole task is to generate a human-like response using the provided information.
Do not use your own knowledge base to generate new information.
Given the user question:
{user_question}

The following result was generated:
{result}

Your task is to generate a human-like response using the question and result above.
The generated response should be as brief as possible. without any explanations. Just provide Question and the result.""",
        )

        config.set(
            "prompt_templates",
            "insights_question_generation_template",
            """You are a seasoned data analyst. Imagine you have access to a database.
Your task is to derive basic insights from the database and generate {n_ques} questions for the same. 
Explore trends, and outliers, and present your findings in a clear and concise manner. 
Keep the generated questions separate and the approach to solve them separate.

Output should be in json format:
{{
response: {{
    questions: {{
        q1: question #1,
        q2: question #2,
        ...
    }}, 
    approach: {{
        q1: approach to solve question #1,
        q2: approach to solve question #2,
        ...
    }}
}}
}}


Make sure that there are at least {n_ques} questions and their approaches.

Assume that the schema for each table is as follows:
=========
[Database schema]
{schema_str}
[Foreign keys]
{fk_str}

Generate questions for getting useful insights from the database schema.""",
        )

        config.set(
            "prompt_templates",
            "decomposer_template",
            """Given a [Database schema] description, a knowledge [Evidence] and the [Question], you need to use valid SQLite and understand the database and knowledge, and then decompose the question into subquestions for text-to-SQL generation.
When generating SQL, we should always consider constraints:
[Constraints]
- Use strftime(<date_column>)
- In `SELECT <column>`, just select needed columns in the [Question] without any unnecessary column or value
- In `FROM <table>` or `JOIN <table>`, do not include unnecessary table
- If use max or min func, `JOIN <table>` FIRST, THEN use `SELECT MAX(<column>)` or `SELECT MIN(<column>)`
- If [Value examples] of <column> has 'None' or None, use `JOIN <table>` or `WHERE <column> is NOT NULL` is better
- If use `ORDER BY <column> ASC|DESC`, add `GROUP BY <column>` before to select distinct values

==========

[Database schema]
# Table: frpm
[
  (CDSCode, CDSCode. Value examples: ['01100170109835', '01100170112607'].),
  (Charter School (Y/N), Charter School (Y/N). Value examples: [1, 0, None]. And 0: N;. 1: Y),
  (Enrollment (Ages 5-17), Enrollment (Ages 5-17). Value examples: [5271.0, 4734.0].),
  (Free Meal Count (Ages 5-17), Free Meal Count (Ages 5-17). Value examples: [3864.0, 2637.0]. And eligible free rate = Free Meal Count / Enrollment)
]
# Table: satscores
[
  (cds, California Department Schools. Value examples: ['10101080000000', '10101080109991'].),
  (sname, school name. Value examples: ['None', 'Middle College High', 'John F. Kennedy High', 'Independence High', 'Foothill High'].),
  (NumTstTakr, Number of Test Takers in this school. Value examples: [24305, 4942, 1, 0, 280]. And number of test takers in each school),
  (AvgScrMath, average scores in Math. Value examples: [699, 698, 289, None, 492]. And average scores in Math),
  (NumGE1500, Number of Test Takers Whose Total SAT Scores Are Greater or Equal to 1500. Value examples: [5837, 2125, 0, None, 191]. And Number of Test Takers Whose Total SAT Scores Are Greater or Equal to 1500. . commonsense evidence:. . Excellence Rate = NumGE1500 / NumTstTakr)
]
[Foreign keys]
frpm.`CDSCode` = satscores.`cds`
[Question]
List school names of charter schools with an SAT excellence rate over the average.
[Evidence]
Charter schools refers to `Charter School (Y/N)` = 1 in the table frpm; Excellence rate = NumGE1500 / NumTstTakr


Decompose the question into sub questions, considering [Constraints], and generate the SQL after thinking step by step:
Sub question 1: Get the average value of SAT excellence rate of charter schools.
SQL
```sql
SELECT AVG(CAST(T2.`NumGE1500` AS REAL) / T2.`NumTstTakr`)
    FROM frpm AS T1
    INNER JOIN satscores AS T2
    ON T1.`CDSCode` = T2.`cds`
    WHERE T1.`Charter School (Y/N)` = 1
```

Sub question 2: List out school names of charter schools with an SAT excellence rate over the average.
SQL
```sql
SELECT T2.`sname`
  FROM frpm AS T1
  INNER JOIN satscores AS T2
  ON T1.`CDSCode` = T2.`cds`
  WHERE T2.`sname` IS NOT NULL
  AND T1.`Charter School (Y/N)` = 1
  AND CAST(T2.`NumGE1500` AS REAL) / T2.`NumTstTakr` > (
    SELECT AVG(CAST(T4.`NumGE1500` AS REAL) / T4.`NumTstTakr`)
    FROM frpm AS T3
    INNER JOIN satscores AS T4
    ON T3.`CDSCode` = T4.`cds`
    WHERE T3.`Charter School (Y/N)` = 1
  )
```

Question Solved.

==========

[Database schema]
# Table: account
[
  (account_id, the id of the account. Value examples: [11382, 11362, 2, 1, 2367].),
  (district_id, location of branch. Value examples: [77, 76, 2, 1, 39].),
  (frequency, frequency of the acount. Value examples: ['POPLATEK MESICNE', 'POPLATEK TYDNE', 'POPLATEK PO OBRATU'].),
  (date, the creation date of the account. Value examples: ['1997-12-29', '1997-12-28'].)
]
# Table: client
[
  (client_id, the unique number. Value examples: [13998, 13971, 2, 1, 2839].),
  (gender, gender. Value examples: ['M', 'F']. And F: female . M: male ),
  (birth_date, birth date. Value examples: ['1987-09-27', '1986-08-13'].),
  (district_id, location of branch. Value examples: [77, 76, 2, 1, 39].)
]
# Table: district
[
  (district_id, location of branch. Value examples: [77, 76, 2, 1, 39].),
  (A4, number of inhabitants . Value examples: ['95907', '95616', '94812'].),
  (A11, average salary. Value examples: [12541, 11277, 8114].)
]
[Foreign keys]
account.`district_id` = district.`district_id`
client.`district_id` = district.`district_id`
[Question]
What is the gender of the youngest client who opened account in the lowest average salary branch?
[Evidence]
Later birthdate refers to younger age; A11 refers to average salary

Decompose the question into sub questions, considering [Constraints], and generate the SQL after thinking step by step:
Sub question 1: What is the district_id of the branch with the lowest average salary?
SQL
```sql
SELECT `district_id`
  FROM district
  ORDER BY `A11` ASC
  LIMIT 1
```

Sub question 2: What is the youngest client who opened account in the lowest average salary branch?
SQL
```sql
SELECT T1.`client_id`
  FROM client AS T1
  INNER JOIN district AS T2
  ON T1.`district_id` = T2.`district_id`
  ORDER BY T2.`A11` ASC, T1.`birth_date` DESC 
  LIMIT 1
```

Sub question 3: What is the gender of the youngest client who opened account in the lowest average salary branch?
SQL
```sql
SELECT T1.`gender`
  FROM client AS T1
  INNER JOIN district AS T2
  ON T1.`district_id` = T2.`district_id`
  ORDER BY T2.`A11` ASC, T1.`birth_date` DESC 
  LIMIT 1 
```
Question Solved.

==========

[Database schema]
{schema_str}
[Foreign keys]
{fk_str}
[Question]
{query}
[Evidence]
{evidence}

Decompose the question into sub questions, considering [Constraints], and generate the SQL after thinking step by step:""",
        )
        config.set(
            "prompt_templates",
            "refiner_template",
            """[Instruction]
When executing SQL below, some errors occurred, please fix up SQL based on query and database info.
Solve the task step by step if you need to. Using SQL format in the code block, and indicate script type in the code block.
When you find an answer, verify the answer carefully. Include verifiable evidence in your response if possible.
[Constraints]
- In `SELECT <column>`, just select needed columns in the [Question] without any unnecessary column or value
- In `FROM <table>` or `JOIN <table>`, do not include unnecessary table
- If use max or min func, `JOIN <table>` FIRST, THEN use `SELECT MAX(<column>)` or `SELECT MIN(<column>)`
- If [Value examples] of <column> has 'None' or None, use `JOIN <table>` or `WHERE <column> is NOT NULL` is better
- If use `ORDER BY <column> ASC|DESC`, add `GROUP BY <column>` before to select distinct values
[Query]
-- {query}
[Evidence]
{evidence}
[Database info]
{schema_str}
[Foreign keys]
{fk_str}
[old SQL]
```sql
{sql}
```
[SQLite error] 
{sqlite_error}
[Exception class]
{exception_class}

Now please fixup old SQL and generate new SQL again.
[correct SQL]""",
        )

        config.add_section("template_questions")
        config.set(
            "template_questions",
            "questions_approaches",
            """{
    "response": {
        "questions": {
            "q1": "What are the top 5 states in order of their total gross sales value of all products?",
            "q2": "What is the average price segment for each product family across all regions?",
            "q3": "Which distribution center has the highest total gross sales value?",
            "q4": "What is the trend of monthly gross sales values for the product family WIRELESS PHONE in the TG region?",
            "q5": "What is the trend of monthly net sales values for a product family GSM HANDSETS IOS in the DEL region?",
        },
        "approach": {
            "q1": "Use the SUM function on the Gross_sale column to get the total gross sales value of all products and GROUP BY clause to group by the STATE column.",
            "q2": "Use the AVG function on the price_segment column grouped by the level3 and level5 columns to get the average price segment for each product family across all regions.",
            "q3": "Use the MAX function on the Gross_sale column where the distribution center matches the desired criteria.",
            "q4": "Use the SUM function on the Gross_sale column grouped by the billing_date_month and level3 columns to get the monthly gross sales values for a specific product family in the TG region. Then, analyze these values over time to see the trend.",
            "q5": "Use the SUM function on the NSWT column grouped by the billing_date_month, level3, and level5 columns to get the monthly net sales values for a specific product family in a specific region. Then, analyze these values over time to see the trend.",
        }
    }
}""",
        )

        return config

    def set_config(self):
        if self._config is None:
            self.create_default_config()
        with open(r"configfile.ini", "w") as configfile:
            self._config.write(configfile)

    def get_config(self):
        if self._config is None:
            self.create_default_config()

        return self._config
