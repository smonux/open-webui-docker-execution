"""
title: DockerInterpreter Tool
author: smonux
author_url: 
version: 0.1.0

This is an openwebui tool that can run arbitrary python(other languages might 
be added the future).

It uses docker tooling and further isolation can be achieved by using
 different docker engines (gVisor's runsc).

The main use case is to couple it with system prompts to implement some
assistants like a data analyst, a coding instructor, etc..

Inspired in 
 https://github.com/EtiennePerot/open-webui-code-execution

The simplest method to make it work it grant access to the unix socket
 that controls docker.
If OpenWebUI is run in a docker machine, it can be done like this
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

OpenWebUI docker image  has the docker python package installed by default.
"""

import asyncio
import docker 
import json
import yaml
import random
import requests
from typing import Callable, Awaitable
from pydantic import BaseModel, Field

run_python_code_description = """
Executes the given Python code and returns the standard output and the standard
error. 

In addition to the standard library, these packages are avalaible:

{packages}

{additional_context}

Files referenced in the prompt without absolute path, should be treated relative
to the current working directory.

It's executed in interactive mode (python -i).

"""

run_python_code_hints = """

:param code: The Python code to execute as a string.
:return: A string containing the combined standard output and error output and the executed code itself
"""

def run_command(code, dockersocket, image, docker_args, timeout=5):
    # Since the interpreter doesn't exit on an exception or a the end of
    # the "file", it must be modified a bit to make it work.
    thecode = f"""

import sys

default_hook = sys.excepthook
def exception_hook(exc_type, exc_value, tb):
    default_hook(exc_type,exc_value,tb)
    sys.exit()

sys.excepthook = exception_hook

{code}

sys.exit()
"""

    unsettable_args  = { 'image' : image,
                        # Hacky, but using PYTHONSTARTUP  requires uploading files to the image
                        'command' :  "python -i -c 'import sys; sys.ps1, sys.ps2 = \"\", \"\"'",
                        'name' : "oai-docker-interpreter-" + str(random.randint(0, 999999999)),
                        'detach' : True,
                        # difference?
                        'remove' : True,
                        'auto_remove' : True,
                        'stdin_open' : True }

    if not set(docker_args).isdisjoint(unsettable_args):
        raise Exception("docker args conflict, these  can't be set by user:" + 
            ",".join(unsettable_args))
    # args which contradicts those  will get overwritten 
    dargs = docker_args.copy()
    dargs.update(unsettable_args)

    try:
        client = docker.DockerClient(base_url = dockersocket) 
    except docker.errors.DockerException as e:
        raise RuntimeError(f"Failed to connect to Docker socket: {e}")

    container = client.containers.run(**dargs)
    s = container.attach_socket( params={'stdin': 1, 'stream': 1, 'stdout':1})
    s._sock.send(thecode.encode("utf-8"))

    try:
        container.wait(timeout = timeout)
        retval = container.logs().decode("utf-8")
    except requests.exceptions.ReadTimeout:
        retval = "Docker execution timed out. Partial output:\n"  +  \
                                    container.logs().decode("utf-8")
        container.stop(1)
    except Exception as e:
        retval = f"Unexpected error: {e}\n" + \
                                    container.logs().decode("utf-8")
        container.stop(1)

    return retval

class Tools:
    class Valves(BaseModel):
        CODE_INTERPRETER_TIMEOUT: int = Field(
            default=120,
            description="The timeout value in seconds for the code interpreter"
                        " subprocess.",
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
            description="The only tested is unix://var/run/docker.sock but "
                        " others could work. If OpenWebUI is run in docker mode "
                        "sharing the host socket should be enough"
        )
        DOCKER_IMAGE: str = Field(
            default="python:3.11-alpine",
            description="docker image to run"
        )
        DOCKER_YAML_OPTIONS : str = Field(
            default=""" 
# See https://docker-py.readthedocs.io/en/stable/containers.html
mem_limit : "1g"
network_disabled : True
working_dir : /mnt
volumes : 
    - "/home/samuel/openwebui-interpreter/shared:/mnt"
            """,
            description="yaml file to configure docker container"
            " https://docker-py.readthedocs.io/en/stable/containers.html"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.yaml_config = yaml.safe_load(self.valves.DOCKER_YAML_OPTIONS)
        self.docker_args = self.yaml_config

        code = """
import importlib.metadata

distributions = importlib.metadata.distributions()
installed_packages = []
for dist in distributions:
    args = (dist.metadata['Name'], dist.version)
    installed_packages.append(args)

for package_name, version in installed_packages:
    print(f"{package_name}=={version}")
"""

        packages = run_command(code = code,
                    dockersocket = self.valves.DOCKER_SOCKET,
                    image = self.valves.DOCKER_IMAGE,
                    docker_args = self.docker_args,
                    timeout= self.valves.CODE_INTERPRETER_TIMEOUT)

        description = run_python_code_description.format(
            packages = packages,
            additional_context=self.valves.ADDITIONAL_CONTEXT
        )

        description = description.replace("\n", ":")
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
        output_template = """
<interpreter_output>
<description>
This is the output of the tool called "DockerInterpreter", appended here for
reference in the response. Use it to answer the query of the user.

The user know use have access to the tool and can inspect your calls, don't 
try to hide it or avoid talking about it.
</description>
<executed_code>
{code}
</executed_code>
<output>
{output}
</output>
</interpreter_output>
"""
        output = ""
        retval = ""
        try:
            output = run_command(code = code,
                    dockersocket = self.valves.DOCKER_SOCKET,
                    image = self.valves.DOCKER_IMAGE,
                    docker_args = self.docker_args,
                    timeout= self.valves.CODE_INTERPRETER_TIMEOUT)

            retval = output_template.format(code = code, output = output)

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
            await __event_emitter__(
                {
                    "type": "message",
                    "data": { "content": f"\n```\n{code}\n```\n```\n{output}```\n"},
                }
            )

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
                    "data": { "content": f"\n```\n{code}\n```\n```\n{e}```\n"},
                }
            )

        return retval


if __name__ == '__main__':
    import sys
    async def _main():
        tool = Tools()
        print(tool.run_python_code.__doc__)
        code = """
import time
import os
time.sleep(10)
print("Hello ---> world")

print(os.listdir())
"""
        async def _dummy_emitter(event):
            print(f"Event: {event}", file=sys.stderr) 
        retval = await tool.run_python_code(code, _dummy_emitter)
        print(retval)

    asyncio.run(_main())
