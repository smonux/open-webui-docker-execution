"""
title: DockerInterpreter Tool
author: smonux
author_url:  https://github.com/smonux/open-webui-docker-execution
version: 0.0.4

This is an openwebui tool that can run arbitrary python(other languages might 
be added the future).

It uses docker tooling and further isolation can be achieved by using
 different docker engines (gVisor's runsc). The openwebui docker image 
has every package needed to run it.

The main use case is to couple it with system prompts to implement some
assistants like a data analyst, a coding instructor, etc... 

It's based/inspired in:
 https://github.com/EtiennePerot/open-webui-code-execution

The simplest method to make it work is to  grant access to the unix socket
that controls docker to oai docker container.

If OpenWebUI is run in a docker machine, it can be done like this in compose:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

BEWARE: The default yaml file shares /tmp with the docker instance. 


The python alpine image is not very useful, you may want to use other,
better equipped image, but pull it first or the UI will freeze.

"""

import datetime
import asyncio
import tarfile
import docker 
import json
import yaml
import random
import io
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

It's executed in non-interactive mode so everything has to be explicitelly printed to stdout to be seen.

"""

run_python_code_hints = """

:param code: The Python code to execute as a string.
:return: A string containing the combined standard output and error output and the executed code itself
"""

list_packages = """
import importlib.metadata

distributions = importlib.metadata.distributions()
installed_packages = []
for dist in distributions:
    args = (dist.metadata['Name'], dist.version)
    installed_packages.append(args)

for package_name, version in installed_packages:
    print(f"{package_name}=={version}")
"""

event_data_template = """
---
<details>
  <summary>Execution: {ts}</summary>

##### Input:
```
{code}
```
##### Output:
```
{output}
```
---

</details>
"""


def run_command(code, dockersocket, image, docker_args, timeout=5):
    unsettable_args  = { 'image' : image,
                        'command' :  "python /tmp/app.py",
                        'name' : "oai-docker-interpreter-" + str(random.randint(0, 999999999)),
                        'detach' : True,
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

    container = client.containers.create(**dargs)
    appfile = io.BytesIO(code.encode('utf-8'))

    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w|') as tar:
        tarinfo = tarfile.TarInfo("app.py")
        tarinfo.size = len(appfile.getvalue())
        appfile.seek(0)
        tar.addfile(tarinfo, appfile)

    container.put_archive("/tmp", stream.getvalue())
    container.start()

    try:
        container.wait(timeout = timeout)
        retval = container.logs().decode("utf-8")
    except requests.exceptions.ReadTimeout:
        retval = "Docker execution timed out. Partial output:\n"  +  \
                                    container.logs().decode("utf-8")
    except Exception as e:
        retval = f"Unexpected error: {e}\n" + \
                                    container.logs().decode("utf-8")
    finally:
        container.stop(timeout = 1)
        container.remove(force = True)

    return retval

class Tools:
    class Valves(BaseModel):
        CODE_INTERPRETER_TIMEOUT: int = Field(
            default=120,
            description="The timeout value in seconds for the code interpreter"
                        " subprocess.",
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
    - "/tmp:/mnt"
            """,
            description="yaml file to configure docker container"
            " https://docker-py.readthedocs.io/en/stable/containers.html"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.yaml_config = yaml.safe_load(self.valves.DOCKER_YAML_OPTIONS)
        self.docker_args = self.yaml_config

        packages = run_command(code = list_packages,
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
        event_description = ""
        try:
            rc_await= asyncio.to_thread(run_command, code = code,
                    dockersocket = self.valves.DOCKER_SOCKET,
                    image = self.valves.DOCKER_IMAGE,
                    docker_args = self.docker_args,
                    timeout= self.valves.CODE_INTERPRETER_TIMEOUT)

            output = await rc_await
            retval = output_template.format(code = code, output = output)
            event_description = "Python code executed successfully"
        except Exception as e:
            output = str(e)
            event_description = f"Error executing Python code: {e}"
        finally:
            await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": event_description,
                            "status": "complete",
                            "done": True,
                            },
                        }
                    )
            await __event_emitter__(
                    {
                        "type": "message",
                        "data": { "content" :  event_data_template.format(code = code,
                                     output = output,
                                     ts = datetime.datetime.now().isoformat()) }})

        return retval
