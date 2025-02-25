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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_API_CALLS = 3

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
             requests_toolkit = RequestsToolkit.from_openapi_spec(openapi_spec)
             tools.extend(requests_toolkit.get_tools())

        except Exception as e:
            print(f"Error creating tools for {filename}: {e}")
    
    # Updated prompt to include a summary of available specs and explicitly tell the agent to use the tools
    template = """
    You are a helpful agent, you have expertise in python, Finance and Risk Management.
    You have access to the following APIs described by these openAPI specs: {spec_names}.
    Use the provided tools to interact with the API.
    You should only use the tools provided. Do not make up function names.

    Available tools:
    {tools}

    Tool names:
    {tool_names}

    Query: {input}
    {agent_scratchpad}
    """
    prompt = PromptTemplate(template=template,
                            input_variables=["input","tools","spec_names","agent_scratchpad","tool_names"])
    
    api_call_counter = 0 
    def _tool_callback(tool,**kwargs):
        nonlocal api_call_counter
        if api_call_counter < MAX_API_CALLS:
            logging.info(f"Hitting endpoint: {kwargs.get('tool_input', {}).get('url', 'No URL Found')}")
            logging.info(f"Parameters: {kwargs.get('tool_input', {}).get('params', 'No Parameters Found')}")
            api_call_counter += 1
        else:
            logging.info("Maximum API call limit reached. No further calls will be made.")

    agent = create_react_agent(llm, tools, prompt)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True, handle_parsing_errors=True, callbacks=[StdOutCallbackHandler(),_tool_callback]) # Added verbose=True for debugging
   
    return agent_executor


def agent_chat(message, history, agent_executor, spec_names):
    """Handles chat input and returns the agent's response."""
    try:
        response = agent_executor.invoke({"input": message, "spec_names": spec_names})
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
        fn=lambda message, history: agent_chat(message, history, agent_executor, spec_names),
        title="ReAct API Agent",
        description="Ask a question related to APIs.",
    )
    iface.launch()


if __name__ == "__main__":
    main()