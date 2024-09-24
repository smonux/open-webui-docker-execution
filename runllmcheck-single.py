import sys
import json
import os
from openai import OpenAI
from dockerinterpreter import Tools
import asyncio
import inspect

def run_llm_check(prompt, model="gpt-4-0613"):
    client = OpenAI()
    tools = Tools()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to multiple Python code interpreter functions. Use the available run_python_code functions when you need to execute Python code. Each function can only be used once."},
        {"role": "user", "content": prompt}
    ]
    
    # Dynamically gather all functions starting with "run_python_code"
    available_functions = [func for func_name, func in inspect.getmembers(tools) if callable(func) and func_name.startswith("run_python_code")]
    used_functions = set()

    def get_available_tools():
        return [
            {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": func.__doc__,
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
            for func in available_functions
            if func.__name__ not in used_functions
        ]

    while True:
        available_tools = get_available_tools()
        if not available_tools:
            break

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
            
            if function_name.startswith("run_python_code"):
                used_functions.add(function_name)
                func = next(func for func in available_functions if func.__name__ == function_name)

                async def _dummy_emitter(event):
                    print(f"Event: {event}", file=sys.stderr)
                code_output = asyncio.run(func(function_args["code"], _dummy_emitter))

                messages.append(response_message)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": code_output,
                    }
                )
            else:
                break
        else:
            break
    
    final_response = client.chat.completions.create(
        model=model,
        messages=messages
    )
    
    return final_response.choices[0].message.content

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python runllmcheck-single.py \"<prompt>\" [<model>]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) == 3 else "gpt-4o-mini"
    
    # OpenAI client will automatically use the OPENAI_API_KEY environment variable
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    result = run_llm_check(prompt, model)
    print(result)
