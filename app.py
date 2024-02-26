from flask import Flask, request
from src.service_context.create_service_context import ServiceContextCreator
from api.api import InsightsAPI, NonLLMAPI, SummaryAPI

app = Flask(__name__)
ServiceContextCreator().set_service_context()
_insights_api = InsightsAPI()
_non_llm_api = NonLLMAPI()
_summary_api = SummaryAPI()


@app.route("/")
def home():
    """
    Home Endpoint

    Returns a welcome message.

    :return: Welcome message
    """
    return "Welcome!"


@app.route("/api/qna", methods=["POST"])
def user_qna():
    """
    User Q&A Endpoint

    Retrieves a response to a user's question using the InsightsAPI.

    :return: JSON response with the answer to the user's question.
    """
    post_data = request.get_json()
    user_question = post_data.get("user_question", "")
    response = _insights_api.get_user_question_response(user_question=user_question)
    return response


@app.route("/api/insights/")
def insights():
    """
    Insights Endpoint

    Retrieves a list of insights using the InsightsAPI.

    :return: JSON response with a list of insights.
    """
    response_list = _insights_api.get_insights()
    return response_list


@app.route("/api/qna_fast", methods=["POST"])
def user_qna_fast():
    """
    Fast User Q&A Endpoint

    Retrieves a fast response to a user's question using the InsightsAPI.

    :return: JSON response with the fast answer to the user's question.
    """
    post_data = request.get_json()
    user_question = post_data.get("user_question", "")
    print(user_question)
    response = _insights_api.get_user_question_response_fast(
        user_question=user_question
    )
    return response


@app.route("/api/qna_template", methods=["POST"])
def user_qna_non_llm():
    post_data = request.get_json()
    user_question = post_data.get("user_question", "")
    print(user_question)
    response = _non_llm_api.get_user_question_response(user_question=user_question)
    return response


@app.route("/api/summary", methods=["POST"])
def summary():
    post_data = request.get_json()
    user_question = post_data.get("user_question", "")
    print(user_question)
    response = _summary_api.get_summary(user_input=user_question)
    return response


if __name__ == "__main__":
    app.run(debug=True)
