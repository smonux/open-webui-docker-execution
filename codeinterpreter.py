"""
title: CodeInterpreter Tool
author: smonux
author_url: 
version: 0.1.0
"""

import asyncio
import subprocess
from typing import Callable, Awaitable
from pydantic import BaseModel, Field

run_python_code_description="""
Executes the given Python code in a subprocess asynchronously and returns the code itself,
the standard output  and the standard error. 

In addition to the standard library it has these packages installed
{predefined_packages}

Files referenced in the prompt without absolute path, should be treated relative to the current working directory.
The subprocess is going to be launched in a specific folder which should contain relevant files.

If matplotlib and mpl_ascii are installed, ascii based plots may be used like this:
import matplotlib;import mpl_ascii; mpl_ascii.ENABLE_COLORS=False;matplotlib.use("module://mpl_ascii")

"""

run_python_code_hints="""

:param code: The Python code to execute as a string.
:return: A string containing the combined standard output and error output and the executed code itself
"""

class Tools:
    class Valves(BaseModel):
        CODE_INTERPRETER_TIMEOUT: int = Field(
            default=120,
            description="The timeout value in seconds for the code interpreter subprocess.",
        )
        SHARED_FILES_PATH: str = Field(
            default="/app/data/shared_files",
            description="The path to the shared files directory."
        )
        PREDEFINED_PACKAGES: list = Field(
            default=["pandas", "numpy", "scipy"],
            description="A list of predefined packages that are not part of the standard library. Install" +
            " matplotib/mpl_ascii for basic plotting and sklearn/statsmodels for data analysis capabilities " ,
        )

    def __init__(self):
        self.valves = self.Valves()

        # The docstring is parsed after instantiation of the Tools, so this should work
        # The parsing doesn't support multiline descriptions (yet) so it has to be in a single line
        description = run_python_code_description.format(
                predefined_packages=", ".join(self.valves.PREDEFINED_PACKAGES))

        description = description.replace("\n", " ")
        Tools.run_python_code.__doc__ = "\n" + description + run_python_code_hints

    async def run_python_code(self, code: str, __event_emitter__: Callable[[dict], Awaitable[None]]) -> str: 
        """docstring placeholder"""
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
                cwd=self.valves.SHARED_FILES_PATH,
                timeout=self.valves.CODE_INTERPRETER_TIMEOUT,
            )

            # Wait for the process to complete and capture output
            stdout, stderr = await process.communicate()
            stdout, stderr = stdout.decode(), stderr.decode()

            # output = stdout.decode() + stderr.decode()

            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Python code executed successfully" + stdout,
                        "status": "complete",
                        "done": True,
                    },
                }
            )
        except Exception as e:
            # Capture and format error output
            stderr = f"Error:\n{e}"

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

            From the point of view of the user, this has been executed by you, so act as if you had run the code  yourself (which is true, just in a previous iteration), so don't say
            you can not run code or don't know what the CodeInterpreter.

            If there is an error the code, also openly acknowledge it, and print the details.

            Always show the stdout and stderr results, besides the code itself.
            
            <description>
            <executed_code>{code}</executed_code>
            <stderr>{stderr}</stderr>
            <stdout>{stdout}</stdout>
        </interpreter_output>
        """
        return output_prompt
