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

run_python_code_description = """
Executes the given Python code in a subprocess asynchronously and returns the code itself,
the standard output  and the standard error. 

In addition to the standard library, all installed packages are available.

{additional_context}

Files referenced in the prompt without absolute path, should be treated relative to the current working directory.
The subprocess is going to be launched in a specific folder which should contain relevant files.

It's executed in script mode, not in interactive mode, so everything has to be explcitelly printed with print(), if some output is needed.
For example if a calculation is needed. The code should be: print(2+2) instead of just sending 2 + 2 to 

If matplotlib and mpl_ascii are installed, there 
import matplotlib;import mpl_ascii;mpl_ascii.ENABLE_COLORS=False; mpl_ascii.AXES_WIDTH=100; mpl_ascii.AXES_HEIGHT=18;matplotlib.use("module://mpl_ascii"); 

"""

run_python_code_hints = """

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
            default="/app/backend/data/shared_files",
            description="The path to the shared files directory.",
        )
        ADDITIONAL_CONTEXT: str = Field(
            default="",
            description="Additional context to be included in the prompt, one line below the predefined packages.",
        )

    def __init__(self):
        self.valves = self.Valves()

        import subprocess
        result = subprocess.run(["pip", "list"], stdout=subprocess.PIPE, text=True)
        installed_packages = [line.split()[0] for line in result.stdout.splitlines()[2:]]
        description = run_python_code_description.format(
            predefined_packages=", ".join(installed_packages),
            additional_context=", ".join(self.valves.ADDITIONAL_CONTEXT),
        )

        description = description.replace("\n", " ")
        Tools.run_python_code.__doc__ = "\n" + description + run_python_code_hints

    async def run_python_code(
        self, code: str, __event_emitter__: Callable[[dict], Awaitable[None]]
    ) -> str:
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
            process = await asyncio.create_subprocess_exec(
                # Execute the code in a subprocess asynchronously
                "python",
                "-u",
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.valves.SHARED_FILES_PATH,
            )

            # Wait for the process to complete and capture output
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.valves.CODE_INTERPRETER_TIMEOUT
            )
            stdout, stderr = stdout.decode(), stderr.decode()

            # output = stdout.decode() + stderr.decode()
            output_prompt = f"""
<interpreter_output>
<description>
This is the output of the tool called "CodeInterpreter", appended here for reference in the response. Use it, properly formatted, to answer the query of the user.
From the point of view of the user, this has been executed by you, so act as if you had run the code  yourself (which is true, just in a previous iteration), so don't say
you can not run code or don't know what the CodeInterpreter is.
                
If there is an error the code, also openly acknowledge it, print the details, and propose solutions.
</description>
<executed_code>
{code}
</executed_code>
<stderr>
{stderr}
</stderr>
<stdout>
{stdout}
</stdout>
</interpreter_output>
"""
            await __event_emitter__(
                {
                    "type": "message",
                    "data": {"content": f"\n```xml\n{output_prompt}```\n"},
                }
            )
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Python code executed successfully",
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

        return output_prompt
