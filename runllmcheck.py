import sys
import json
import openai
from dockerinterpreter import Tools

def run_llm_check(prompt):
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
        model="gpt-3.5-turbo-0613",
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
                model="gpt-3.5-turbo-0613",
                messages=messages
            )
            
            return second_response["choices"][0]["message"]["content"]
    else:
        return response_message["content"]

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python runllmcheck.py \"<prompt>\"")
        sys.exit(1)
    
    prompt = sys.argv[1]
    result = run_llm_check(prompt)
    print(result)
