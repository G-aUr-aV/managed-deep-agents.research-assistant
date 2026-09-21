import os

from langchain_openai import ChatOpenAI
from managed_deepagents import define_deep_agent

from tools.context7 import context7_docs
from tools.papers import paper_search
from tools.search import internet_search

model = ChatOpenAI(
    model=os.environ["DEEPINFRA_MODEL"],
    base_url="https://api.deepinfra.com/v1",
    api_key=os.environ["DEEPINFRA_API_KEY"],
)

agent = define_deep_agent(
    name="research-assistant-preview",
    model=model,
    tools=[internet_search, paper_search, context7_docs],
)
