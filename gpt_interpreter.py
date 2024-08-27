"""
title: GPT Interpreter Tool
author: YourName
author_url: https://github.com/YourUsername/YourRepository
version: 0.1.0
"""

import asyncio
import subprocess

class Tools:
    async def run_python_code(self, code: str) -> str:
        """
        Executes the given Python code in a subprocess asynchronously and returns the standard output and error output as monospaced text.
        
        :param code: The Python code to execute as a string.
        :return: A string containing the combined standard output and error output formatted as monospaced text.
        """
        try:
            # Execute the code in a subprocess asynchronously
            process = await asyncio.create_subprocess_exec(
                'python', '-c', code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for the process to complete and capture output
            stdout, stderr = await process.communicate()
            output = stdout.decode() + stderr.decode()
        except subprocess.CalledProcessError as e:
            # Capture and format error output
            output = f"Error:\n{e.stderr}"
        
        # Format output as monospaced text
        return f"```\n{output}\n```"
