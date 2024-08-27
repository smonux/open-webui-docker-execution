"""
title: GPT Interpreter Tool
author: YourName
author_url: https://github.com/YourUsername/YourRepository
version: 0.1.0
"""

import subprocess

class Tool:
    def run_python_code(self, code: str) -> str:
        """
        Executes the given Python code in a subprocess and returns the standard output and error output as monospaced text.
        
        :param code: The Python code to execute as a string.
        :return: A string containing the combined standard output and error output formatted as monospaced text.
        """
        try:
            # Execute the code in a subprocess
            result = subprocess.run(
                ['python', '-c', code],
                capture_output=True,
                text=True,
                check=True
            )
            # Combine standard output and error output
            output = result.stdout + result.stderr
        except subprocess.CalledProcessError as e:
            # Capture and format error output
            output = f"Error:\n{e.stderr}"
        
        # Format output as monospaced text
        return f"```\n{output}\n```"
