"""
title: DockerInterpreter Tool
author: smonux
author_url: 
version: 0.1.0

This is an openwebui tool that can run arbitrary python(other languages might be supported in the future)

Further isolation can be achieved by using different docker engines (gVisor).

Inspired in 
 https://github.com/EtiennePerot/open-webui-code-execution

The simplest method to make it work it grant access to the unix socket that controls docker.
If OpenWebUI is run in a docker machine, it can be done like this
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

OpenWebUI docker image (it has the docker python package installed by default).
"""

import asyncio
import docker 
import json
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
            description="Additional context to be included in the tool description.",
        )
        DOCKER_SOCKET: str = Field(
            default="unix://var/run/docker.sock",
            description="The only tested is unix://var/run/docker.sock but others could work. If OpenWebUI is run in docker mode "
            "sharing the host socket should be enough"
        )
        DOCKER_IMAGE: str = Field(
            default="python:3.11",
            description="image to run"
        )
        DOCKER_YAML_OPTIONS : str = Field(
            default="""
# See https://docker-py.readthedocs.io/en/stable/containers.html
            """,
            description="yaml file to configure docker container https://docker-py.readthedocs.io/en/stable/containers.html"
        )

    def __init__(self):
        self.valves = self.Valves()

        description = run_python_code_description.format(
            additional_context=", ".join(self.valves.ADDITIONAL_CONTEXT)
        )

        description = description.replace("\n", " ")
        Tools.run_python_code.__doc__ = "\n" + description + run_python_code_hints
        client = docker.DockerClient(base_url = self.valves.DOCKER_SOCKET) 
        retval = client.containers.run(self.valves.DOCKER_IMAGE,
                                       command =  "pip list --format json",
                                       name = "oai-docker-execution")
        retvaljs = json.loads(retval.decode("utf-8"))
        packages = [ p['name'] + "-" + p['version'] for p in retvaljs ]

        self.debug_info = packages

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
        output_template = """
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
        stdout, stderr = "NO stdout", "NO stderr"
        try:
            process = await asyncio.create_subprocess_exec(
                # Execute the code in a subprocess asynchronously
                "python",
                "-u",
                "-c",
                code.encode("utf-8"),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.valves.SHARED_FILES_PATH,
            )

            # Wait for the process to complete and capture output
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.valves.CODE_INTERPRETER_TIMEOUT
            )
            stdout, stderr = stdout.decode("utf-8"), stderr.decode("utf-8")

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
            output  = output_template.format(code = code, stderr = stderr, stdout = stdout)
        except Exception as e:
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
        

        await __event_emitter__(
                {
                    "type": "message",
                    "data": {"content": f"\n```xml\n{output}```\n"},
                }
            )

        return output
