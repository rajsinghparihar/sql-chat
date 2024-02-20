from flask import Flask, request
from src.service_context.create_service_context import ServiceContextCreator
from api.api import InsightsAPI

app = Flask(__name__)
ServiceContextCreator().set_service_context()
_insights_api = InsightsAPI()


@app.route("/")
def home():
    return "Welcome!"


@app.route("/api/qna", methods=["POST"])
def user_qna():
    post_data = request.get_json()
    user_question = post_data.get("user_question", "")
    response = _insights_api.get_user_question_response(user_question=user_question)
    return response


@app.route("/api/insights/")
def insights():
    response_list = _insights_api.get_insights()
    return response_list


@app.route("/api/qna_fast", methods=["POST"])
def user_qna_fast():
    post_data = request.get_json()
    user_question = post_data.get("user_question", "")
    print(user_question)
    response = _insights_api.get_user_question_response_fast(
        user_question=user_question
    )
    return response


if __name__ == "__main__":
    app.run(debug=True)
