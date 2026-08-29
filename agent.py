import os

from langchain_openai import ChatOpenAI
from managed_deepagents import define_deep_agent

from tools.search import internet_search
from tools.customer import lookup_customer

model = ChatOpenAI(
    model="deepseek-ai/DeepSeek-V4-Flash-0731",
    base_url="https://api.deepinfra.com/v1",
    api_key=os.environ["DEEPINFRA_API_KEY"],
)

agent = define_deep_agent(
    name="research-assistant-preview",
    model=model,
    tools=[internet_search, lookup_customer],
)