import os
import yaml
from dotenv import load_dotenv
import gradio as gr
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.openapi import OpenAPISpec
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks import StdOutCallbackHandler
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict

#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG_FILE = "agent.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # Also print to console
    ]
)


# MAX_API_CALLS = 3
# MAX_RETRIES = 2 # Maximum number of retries for each API call

# class APICallbackHandler(BaseCallbackHandler):
#     """Custom callback handler to log API calls and limit usage."""

#     def __init__(self, max_calls: int = MAX_API_CALLS, max_retries: int = MAX_RETRIES):
#         super().__init__()
#         self.api_call_counter = 0
#         self.max_calls = max_calls
#         self.max_retries = max_retries
#         self.session = requests.Session()
#         retry = Retry(total=max_retries, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
#         adapter = HTTPAdapter(max_retries=retry)
#         self.session.mount("http://", adapter)
#         self.session.mount("https://", adapter)

#     def on_tool_start(self, tool, input_str, **kwargs):
#         if self.api_call_counter < self.max_calls:
#             try:
#                 url = kwargs.get('tool_input', {}).get('url', 'No URL Found')
#                 params = kwargs.get('tool_input', {}).get('params', 'No Parameters Found')
#                 logging.info(f"Hitting endpoint: {url}")
#                 logging.info(f"Parameters: {params}")
                
#                 # Make the API call with retries
#                 response = self.session.request(method=kwargs.get('tool_input', {}).get('method', 'get'),url=url, params=params)
#                 response.raise_for_status()
#                 logging.info(f"API call successful")
#                 self.api_call_counter += 1

#             except requests.exceptions.RequestException as e:
#                 logging.error(f"API call failed after {self.max_retries} retries. Error: {e}")
#         else:
#            logging.info("Maximum API call limit reached. No further calls will be made.")
#         return super().on_tool_start(tool, input_str, **kwargs)

#     def on_tool_end(self, tool, output, **kwargs):
#         logging.info(f"Finished tool: {tool.name}")
#         logging.info(f"Tool output: {output}")
#         return super().on_tool_end(tool, output, **kwargs)


def load_yaml_specs(folder_path):
    """Loads all YAML files from a folder."""
    specs = {}
    for filename in os.listdir(folder_path):
        if filename.endswith((".yaml", ".yml")):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r') as f:
                    spec = yaml.safe_load(f)
                    specs[filename] = spec
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    return specs

def create_agent_with_specs(specs, llm):
    """Creates a ReAct agent with the provided OpenAPI specs."""
    tools = []
    for filename, spec in specs.items():
        try:
             openapi_spec = OpenAPISpec.from_spec_dict(spec)
             requests_toolkit = RequestsToolkit(allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST).from_openapi_spec(openapi_spec)
             tools.extend(requests_toolkit.get_tools())

        except Exception as e:
            print(f"Error creating tools for {filename}: {e}")
    
    # Updated prompt to include a summary of available specs and explicitly tell the agent to use the tools
    template = """
    You have expertise in python, Finance and Risk Management.
    You have access to the APIs described by these openAPI specs: {specs}.
    you should Trigger relevant API endpoints based on user query.
    Provide user complete information on what is being triggered and what is the response.

    Available tools:
    {tools}

    Tool names:
    {tool_names}

    Query: {input}
    {agent_scratchpad}
    """
    prompt = PromptTemplate(template=template,
                            input_variables=["input","tools","specs","agent_scratchpad","tool_names"])
    
    agent = create_react_agent(llm, tools, prompt)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    # api_callback_handler = APICallbackHandler()
    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True, handle_parsing_errors=True, callbacks=[StdOutCallbackHandler()]) # Added verbose=True for debugging
    # agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True, handle_parsing_errors=True, callbacks=[StdOutCallbackHandler(), api_callback_handler]) # Added verbose=True for debugging
   
   
    return agent_executor


def agent_chat(message, history, agent_executor, specs):
    """Handles chat input and returns the agent's response."""
    try:
        response = agent_executor.invoke({"input": message, "specs": specs})
        return response["output"]
    except Exception as e:
       return f"An error occurred: {e}"

def main():
    """Main function to run the Gradio interface."""

    load_dotenv(override=True)
    openai_api_key = os.getenv('OPENAI_API_KEY')
    folder_path = "open_api_specs"  # Current folder. Change if your YAML files are elsewhere
    specs = load_yaml_specs(folder_path)
    if not specs:
        print("No valid OpenAPI specs found. Exiting...")
        return

    spec_names = ", ".join(specs.keys())
    print(f"Loaded OpenAPI specs: {spec_names}")


    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent_executor = create_agent_with_specs(specs, llm)


    iface = gr.ChatInterface(
        fn=lambda message, history: agent_chat(message, history, agent_executor, specs),
        title="ReAct API Agent",
        description="Ask a question related to APIs.",
    )
    iface.launch()


if __name__ == "__main__":
    main()