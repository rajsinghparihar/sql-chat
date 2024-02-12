from flask import Flask
from src.service_context.create_service_context import ServiceContextCreator
from api.api import BaseAPI, InsightsAPI


app = Flask(__name__)
_base_api = None
_insights_api = None

def initialize():
    global _base_api, _insights_api
    ServiceContextCreator().set_service_context()
    _base_api = BaseAPI()
    _insights_api = InsightsAPI()

@app.route("/")
def home():
    initialize()
    return "Welcome!"

@app.route("/api/qna/<user_question>")
def user_qna(user_question):
    response = _base_api.get_user_question_response(user_question=user_question)
    return response

@app.route("/api/insights/")
def insights():
    response_list = _insights_api.get_insights()
    return response_list
    
if __name__ == "__main__":
    app.run(debug=True)
