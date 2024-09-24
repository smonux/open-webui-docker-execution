import sys
import json
import os
from openai import OpenAI
from dockerinterpreter import Tools
import asyncio
import argparse
import pprint

def run_llm_check(prompt, model="gpt-4-0613", max_iterations=3):
    client = OpenAI()
    tools = Tools()
    
    # Get the number of available run_python_code_* functions
    available_functions = [func for func in dir(tools) if func.startswith("run_python_code_")]
    max_iterations = len(available_functions)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to multiple Python code interpreter functions. Use the run_python_code_* functions when you need to execute Python code, where * is a number."},
        {"role": "user", "content": prompt}
    ]
    
    available_tools = [
        {
            "type": "function",
            "function": {
                "name": func,
                "description": getattr(tools, func).__doc__,
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
    ]
    
    for iteration in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=available_tools
        )
        
        response_message = response.choices[0].message
        messages.append(response_message)
        
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            if function_name in available_functions:
                async def _dummy_emitter(event):
                    print(f"Event: {event}", file=sys.stderr) 
                code_output = asyncio.run(getattr(tools, function_name)(function_args["code"], _dummy_emitter))

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": code_output,
                    }
                )
        else:
            # If no function was called, we're done
            break
    second_response = client.chat.completions.create(
                model=model,
                messages=messages
    )
    # Return the last message from the assistant
    return second_response.choices[0].message.content

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLM check with multiple function calls.")
    parser.add_argument("prompt", help="The prompt to send to the LLM")
    parser.add_argument("--model", default="gpt-4o-mini", help="The model to use (default: gpt-4o-mini)")
    args = parser.parse_args()
    
    # OpenAI client will automatically use the OPENAI_API_KEY environment variable
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    result = run_llm_check(args.prompt, args.model)
    print(result)
