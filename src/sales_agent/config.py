import os

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

# llm = ChatOllama(model='llama3.1')
llm = ChatOpenAI(model='gpt-4o', api_key=os.getenv('OPENAI_API_KEY)'))
llm_with_reasoning = ChatOpenAI(model='gpt-4o', api_key=os.getenv('OPENAI_API_KEY)'))

SLEEP_TIME = 2
HIL_FLAG = False