import os
import yaml
from dotenv import load_dotenv
import gradio as gr
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_community.utilities.openapi import OpenAPISpec
from langchain_openai import ChatOpenAI
from langchain_experimental.tools.python.tool import PythonREPLTool
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.callbacks import StdOutCallbackHandler
import logging

LOG_FILE = "agent.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # Also print to console
    ]
)

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

python_repl = PythonREPLTool()

def create_agent_with_specs(specs, llm):
    """Creates a ReAct agent with the provided OpenAPI specs."""
    tools = []
    for filename, spec in specs.items():
        try:
             openapi_spec = OpenAPISpec.from_spec_dict(spec)
            #  requests_toolkit = RequestsToolkit(allow_dangerous_requests=True).from_openapi_spec(openapi_spec)
            #  tools.extend(requests_toolkit.get_tools())
        except Exception as e:
            print(f"Error creating tools for {filename}: {e}")
    tools.append(python_repl)
    # Updated prompt to include a summary of available specs and explicitly tell the agent to use the tools
    template = """
    You read openAPI specifications from {specs}.
    Based on user's Query: {input} you generate python code to hit correct API endpoint. 
    You can execute code, use available tools {tool_names} and API is accessible {tools} {agent_scratchpad} 
    You present response to the user in a readable format.
    """
    prompt = PromptTemplate(template=template,
                            input_variables=["specs","input","tool_names","tools","agent_scratchpad"])
    agent = create_react_agent(llm, tools, prompt)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True, handle_parsing_errors=True, callbacks=[StdOutCallbackHandler()]) # Added verbose=True for debugging
    return agent_executor

def agent_chat(message, history, agent_executor, specs):
    """Handles chat input and returns the agent's response."""
    try:
        response = agent_executor.invoke({"input": message, "specs": specs, "tools": agent_executor.tools, "tool_names": [tool.name for tool in agent_executor.tools]})
        # response = agent_executor.invoke({"input": message})
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
        title="Pulsar",
        description="Ask a question related to APIs.",
        type="messages"
    )
    iface.launch()


if __name__ == "__main__":
    main()