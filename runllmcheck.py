import sys
import json
import os
from openai import OpenAI
from dockerinterpreter import Tools
import asyncio

def run_llm_check(prompt, model="gpt-4-0613"):
    client = OpenAI()
    tools = Tools()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to a Python code interpreter. Use the run_python_code function when you need to execute Python code."},
        {"role": "user", "content": prompt}
    ]
    
    available_tools = [
        {
            "type": "function",
            "function": {
                "name": "run_python_code",
                "description": tools.run_python_code.__doc__,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The Python code to execute"
                        }
                    },
                    "required": ["code"]
                }
            }
        }
    ]
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=available_tools,
        tool_choice="auto"
    )
    
    response_message = response.choices[0].message
    
    if response_message.tool_calls:
        tool_call = response_message.tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        if function_name == "run_python_code":

            async def _dummy_emitter(event):
                print(f"Event: {event}", file=sys.stderr) 
            code_output = asyncio.run(tools.run_python_code(function_args["code"], _dummy_emitter))

            messages.append(response_message)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": code_output,
                }
            )
            
            second_response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            return second_response.choices[0].message.content
    else:
        return response_message.content

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python runllmcheck.py \"<prompt>\" [<model>]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) == 3 else "gpt-4o-mini"
    
    # OpenAI client will automatically use the OPENAI_API_KEY environment variable
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    result = run_llm_check(prompt, model)
    print(result)
