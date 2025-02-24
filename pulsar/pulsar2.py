import os
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
from run_logic import read_openapi_specs, create_api_scripts, execute_script

load_dotenv(override=True)
openai_api_key = os.getenv('OPENAI_API_KEY')
if openai_api_key:
    print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
else:
    print("OpenAI API Key not set")
openai = OpenAI()
MODEL = 'gpt-4o-mini'

system_message = "You are a Finance and Risk Management expert with expert python skills."
system_message += "You are tasked with responding to credit officers questions."
system_message += "You have access to open API specifications of the application."
system_message += "You will interpret user questions and write python code to trigger corresponding REST endpoints."
system_message += "Once python execution completed you will display the response to the user in a easily understandble format."


def chat(message,history):
    specs = read_openapi_specs("swagger_yamls")

    messages = [{"role": "system", "content": system_message}] + history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(
        model=MODEL,
        messages=messages
    )
    script = response.choices[0].message.content
    execute_script(script)

gr.ChatInterface(fn=chat, title="Pulsar Chatbot", type="messages",description="Explore SuperNova with Pulsar").launch()
