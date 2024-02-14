**SLLM Chat**

Setup:

Download llm model file from [here](https://huggingface.co/TheBloke/laser-dolphin-mixtral-2x7b-dpo-GGUF/blob/main/laser-dolphin-mixtral-2x7b-dpo.Q4_K_M.gguf)
keep it in `models/` directory.

Download data files from [here](https://rilcloud-my.sharepoint.com/:f:/g/personal/raj2_parihar_ril_com/Ekb1pYNsSRpDitOlTENf8owBK02sKK2c6GZTDz5O1o89KQ?e=dffbPQ)
keep them `data/csv` and `data/db` directories accordingly.

```
pip install -r requirements.txt
```

Running:

```
python app.py
```

Endpoints:

- `/` -> Homepage (initializes the llm and sets up the service context)
- `/api/qna/<user_question>` -> basic question and answering
- `/api/insights` -> insight generation based on template questions
