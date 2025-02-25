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

# Load environment variables from .env file
load_dotenv()

# Set the OpenAI API key using the environment variable
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_API_CALLS = 3
MAX_RETRIES = 2 # Maximum number of retries for each API call

class APICallbackHandler(BaseCallbackHandler):
    """Custom callback handler to log API calls and limit usage."""

    def __init__(self, max_calls: int = MAX_API_CALLS, max_retries: int = MAX_RETRIES):
        super().__init__()
        self.api_call_counter = 0
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.session = requests.Session()
        retry = Retry(total=max_retries, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def on_tool_start(self, tool, input_str, **kwargs):
        if self.api_call_counter < self.max_calls:
            try:
                url = kwargs.get('tool_input', {}).get('url', 'No URL Found')
                params = kwargs.get('tool_input', {}).get('params', 'No Parameters Found')
                logging.info(f"Hitting endpoint: {url}")
                logging.info(f"Parameters: {params}")
                
                # Make the API call with retries
                response = self.session.request(method=kwargs.get('tool_input', {}).get('method', 'get'),url=url, params=params)
                response.raise_for_status()
                logging.info(f"API call successful")
                self.api_call_counter += 1

            except requests.exceptions.RequestException as e:
                logging.error(f"API call failed after {self.max_retries} retries. Error: {e}")
        else:
           logging.info("Maximum API call limit reached. No further calls will be made.")
        return super().on_tool_start(tool, input_str, **kwargs)


def load_yaml_specs(folder_path) -> Dict[str, dict]:
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


def create_agent_with_specs(specs: Dict[str, dict], llm: ChatOpenAI) -> AgentExecutor:
    """Creates a ReAct agent with the provided OpenAPI specs."""
    tools = []
    for filename, spec in specs.items():
        try:
             openapi_spec = OpenAPISpec.from_spec_dict(spec)
             requests_toolkit = RequestsToolkit.from_openapi_spec(openapi_spec)
             tools.extend(requests_toolkit.get_tools())

        except Exception as e:
            print(f"Error creating tools for {filename}: {e}")
    
    # Updated prompt to include a summary of available specs and explicitly tell the agent to use the tools
    template = """
    You are a helpful agent, you have expertise in python, Finance and Risk Management.
    You have access to the following APIs described by these openAPI specs: {spec_names}.
    Use the tools available to answer the query.
    You should only use the tools provided. Do not make up function names.

    Available tools:
    {tools}

    Tool names:
    {tool_names}

    Query: {input}
    {agent_scratchpad}
    """
    prompt = PromptTemplate(
        template=template,
        input_variables=["input", "tools", "spec_names", "agent_scratchpad", "tool_names"]
    )

    agent = create_react_agent(llm, tools, prompt)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    # Create the callback handler
    api_callback_handler = APICallbackHandler()

    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True, callbacks=[StdOutCallbackHandler(), api_callback_handler])

    return agent_executor

def main():
    """Main function to run the agent."""
    folder_path = "open_api_specs"  # Current folder. You can change this if the yaml files are in a different location
    specs = load_yaml_specs(folder_path)
    if not specs:
        print("No valid OpenAPI specs found. Exiting...")
        return

    spec_names = ", ".join(specs.keys())
    print(f"Loaded OpenAPI specs: {spec_names}")
    
    # Initialize ChatOpenAI with the API key from the environment variable
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=os.environ.get("OPENAI_API_KEY"))  # Or any other LLM of your choice
    agent_executor = create_agent_with_specs(specs, llm)

    def predict(input, spec_names):
       try:
          response = agent_executor.invoke({"input": input, "spec_names": spec_names})
          return response["output"]
       except Exception as e:
            return f"An error occurred: {e}"

    iface = gr.Interface(
        fn=predict,
        inputs=[
            gr.Textbox(lines=7, label="Enter your query"),
            gr.Textbox(value=spec_names, visible=False)
        ],
        outputs=gr.Textbox(label="Response"),
        title="OpenAPI Agent",
        description="Ask a question about the apis, the agent will call the tools and answer your questions."
    )

    iface.launch(share=False)
    
if __name__ == "__main__":
    main()