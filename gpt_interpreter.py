"""
title: GPT Interpreter Tool
author: YourName
author_url: 
version: 0.1.0
"""

import asyncio
import subprocess
from typing import Callable, Awaitable


class Tools:
    async def run_python_code(
        self, code: str, __event_emitter__: Callable[[dict], Awaitable[None]]
    ) -> str:
        """
        Executes the given Python code in a subprocess asynchronously and returns the code itself,  the standard output 
        and the standard error.
        
        Python version is Python 3.11.9 and the operating system is a Linux docker image.
        
        It may be used to respond to data analysis queries.
        :param code: The Python code to execute as a string.
        :return: A string containing the combined standard output and error output formatted as monospaced text.
        """
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Executing Python code",
                    "status": "in_progress",
                    "done": False,
                },
            }
        )
        stdout, stderr = "NO stdout", "NO stderr"
        try:
            # Execute the code in a subprocess asynchronously
            process = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for the process to complete and capture output
            stdout, stderr = await process.communicate()
            # output = stdout.decode() + stderr.decode()

            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Python code executed successfully" + code,
                        "status": "complete",
                        "done": True,
                    },
                }
            )
        except subprocess.CalledProcessError as e:
            # Capture and format error output
            stderr = f"Error:\n{e.stderr}"

            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Error executing Python code: {e}",
                        "status": "complete",
                        "done": True,
                    },
                }
            )

        # Format output

        output_prompt = f"""
        <interpreter_output>
            <description>This is the output of the tool called "CodeInterpreter", appended here for reference in the response. Use it, properly formatted, to answer the query of the user.
            
            <description>
            <executed_code>{code}</executed_code>
            <stderr>{stderr}</stderr>
            <stdout>{stdout}</stdout>
        </interpreter_output>
        """
        return output_prompt
