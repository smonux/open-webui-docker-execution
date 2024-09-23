import sys
import json
import os
import openai
from dockerinterpreter import Tools

def run_llm_check(prompt, model="gpt-4-0613"):
    tools = Tools()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to a Python code interpreter. Use the run_python_code function when you need to execute Python code."},
        {"role": "user", "content": prompt}
    ]
    
    functions = [
        {
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
    ]
    
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        functions=functions,
        function_call="auto"
    )
    
    response_message = response["choices"][0]["message"]
    
    if response_message.get("function_call"):
        function_name = response_message["function_call"]["name"]
        function_args = json.loads(response_message["function_call"]["arguments"])
        
        if function_name == "run_python_code":
            code_output = tools.run_python_code(function_args["code"])
            messages.append(response_message)
            messages.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": code_output,
                }
            )
            
            second_response = openai.ChatCompletion.create(
                model=model,
                messages=messages
            )
            
            return second_response["choices"][0]["message"]["content"]
    else:
        return response_message["content"]

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python runllmcheck.py \"<prompt>\" [<model>]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) == 3 else "gpt-4o-mini"
    
    # Set OpenAI API key from environment variable
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    result = run_llm_check(prompt, model)
    print(result)
