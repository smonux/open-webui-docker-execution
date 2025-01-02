"""
title: DockerInterpreter Tool (R only)
author: smonux
version: 0.0.5

This code allows executing R instructions inside a Docker container.
"""

import datetime
import asyncio
import tarfile
import docker
import yaml
import random
import io
import requests
import base64
from typing import Callable, Awaitable
from pydantic import BaseModel, Field
import os
import uuid
from pathlib import Path

try:
    from openwebui.config import CACHE_DIR
except Exception:
    print("Setting CACHE_DIR to 'data'")
    CACHE_DIR = "data/cache"

IMAGE_CACHE_DIR = Path(CACHE_DIR).joinpath("./image/generations/")
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Template used to report execution logs and metadata
event_data_template = """
---
<details>
  <summary>Execution: {ts}</summary>

##### Input:
```r
{code}
```

##### Output:
```
{output}
```


#### Generated images:

{images_as_md}
---

</details>
"""

# R prefix code to capture plots as .jpg
r_plot_template = r"""
try({
  # For better rendering inside containers
  options(bitmapType='cairo')
  plot_dir <- "/tmp/"
  on.exit({
    dev.list.all <- dev.list()
    if (!is.null(dev.list.all) && length(dev.list.all) > 0) {
      for (dev_num in dev.list.all) {
        dev.set(dev_num)
        # Copy the current device to a JPEG file
        dev.copy(
          jpeg,
          filename = file.path(plot_dir, paste0("plot_", dev_num, ".jpg")),
          quality = {jpeg_compression},
          width = as.integer(strsplit("{image_size}", "x")[[1]][1]),
          height = as.integer(strsplit("{image_size}", "x")[[1]][2]),
          units = "px"
        )
        dev.off()
      }
    }
  }, add=TRUE)
}, silent=TRUE)

"""

# Template for final output
output_template = """
<interpreter_output>
<description>
This is the output of the tool called "DockerInterpreter (R only)", appended here for
reference in the response. Use it to answer the query of the user.
</description>
<executed_code>
{code}
</executed_code>
<output>
{output}
</output>
</interpreter_output>
"""


def extract_images(container, plot_dir):
    """
    Extracts JPG files generated in the container, converts them to base64,
    and returns the resulting data URIs.
    """
    images = []
    try:
        tar_stream, _ = container.get_archive(plot_dir)
        tar_data = b""
        for chunk in tar_stream:
            tar_data += chunk

        with tarfile.open(fileobj=io.BytesIO(tar_data), mode="r") as tar:
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith(".jpg"):
                    figure_file = tar.extractfile(member)
                    if figure_file:
                        figure_data = figure_file.read()
                        figure_base64 = base64.b64encode(figure_data).decode("utf-8")
                        images.append(f"data:image/jpeg;base64,{figure_base64}")
    except Exception as e:
        print(f"Failed to retrieve figures: {e}")

    return images


def run_command_r(
    code,
    dockersocket,
    image,
    docker_args,
    timeout=5,
    enable_image_generation=True,
    image_size="512x512",
    jpeg_compression=90,
):
    """
    Executes R code inside a Docker container.
    Returns a dict with:
      "output": string containing stdout/stderr
      "images": list of image data in base64
    """
    PLOT_DIR = "/tmp/"
    # Add prefix code for capturing R plots
    if enable_image_generation:
        code = (
            r_plot_template.format(
                image_size=image_size, jpeg_compression=jpeg_compression
            )
            + code
        )

    # Docker arguments for R execution
    unsettable_args = {
        "image": image,
        "command": "Rscript /tmp/app.R",
        "name": "oai-docker-interpreter-R-" + str(random.randint(0, 999999999)),
        "detach": True,
        "stdin_open": True,
    }
    if not set(docker_args).isdisjoint(unsettable_args):
        raise Exception(
            "docker args conflict, these can't be set by user: "
            + ", ".join(unsettable_args)
        )
    dargs = docker_args.copy()
    dargs.update(unsettable_args)

    # Connect to Docker
    try:
        client = docker.DockerClient(base_url=dockersocket)
    except docker.errors.DockerException as e:
        raise RuntimeError(f"Failed to connect to Docker socket: {e}")

    # Create the container
    container = client.containers.create(**dargs)

    # Upload the R script (app.R) to the container
    appfile = io.BytesIO(code.encode("utf-8"))
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w|") as tar:
        tarinfo = tarfile.TarInfo("app.R")
        tarinfo.size = len(appfile.getvalue())
        appfile.seek(0)
        tar.addfile(tarinfo, appfile)

    container.put_archive("/tmp", stream.getvalue())
    container.start()

    # Execute, wait for completion, and gather logs and images
    try:
        container.wait(timeout=timeout)
        retval = container.logs().decode("utf-8")
        images = extract_images(container, PLOT_DIR)
    except requests.exceptions.ReadTimeout:
        retval = (
            "Docker execution timed out. Partial output:\n"
            + container.logs().decode("utf-8")
        )
        images = []
    except Exception as e:
        retval = f"Unexpected error: {e}\n" + container.logs().decode("utf-8")
        images = []
    finally:
        container.stop(timeout=1)
        container.remove(force=True)

    return {"output": retval, "images": images}


class Tools:
    class Valves(BaseModel):
        CODE_INTERPRETER_TIMEOUT: int = Field(
            default=120,
            description="Timeout (in seconds) for executing R code in Docker.",
        )
        ADDITIONAL_CONTEXT: str = Field(
            default="",
            description="Additional context to be included in the tool description.",
        )
        DOCKER_SOCKET: str = Field(
            default="unix://var/run/docker.sock",
            description="Path or URL for Docker socket (tested with unix://var/run/docker.sock).",
        )
        # Default R image
        DOCKER_IMAGE_R: str = Field(
            default="rocker/tidyverse",
            description="Docker image used to run R code.",
        )
        DOCKER_YAML_OPTIONS: str = Field(
            default="""
    mem_limit : "1g"
    network_disabled : True
    working_dir : /mnt
    volumes :
        - "/home/samuel/hosting/shared_files:/mnt"
            """,
            description="YAML string with docker-py options for the container.",
        )
        ENABLE_IMAGE_GENERATION: bool = Field(
            default=True,
            description="Enable or disable image generation.",
        )

    def __init__(self):
        # Read YAML config for Docker arguments
        self.valves = self.Valves()
        self.yaml_config = yaml.safe_load(self.valves.DOCKER_YAML_OPTIONS)
        self.docker_args = self.yaml_config

    async def run_r_code(
        self,
        code: str,
        __event_emitter__: Callable[[dict], Awaitable[None]],
        __messages__: list[dict],
        __model__: str,
    ) -> str:
        """
        Executes R code in a Docker container and returns the result along with
        any generated images.

        :param code: R code as a string
        :return: String containing stdout, stderr, and the executed code
        """
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Executing R code",
                    "status": "in_progress",
                    "done": False,
                },
            }
        )

        enable_image_generation = self.valves.ENABLE_IMAGE_GENERATION
        output = ""
        retval = ""
        event_description = ""
        image_names = []

        try:
            rc_await = asyncio.to_thread(
                run_command_r,
                code=code,
                dockersocket=self.valves.DOCKER_SOCKET,
                image=self.valves.DOCKER_IMAGE_R,
                docker_args=self.docker_args,
                timeout=self.valves.CODE_INTERPRETER_TIMEOUT,
                enable_image_generation=enable_image_generation,
            )
            vals = await rc_await
            output = vals["output"]
            images = vals["images"]
            retval = output_template.format(code=code, output=output)

            # Insert images into the message history
            new_message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Images generated by the run_r_code tool",
                    }
                ],
            }
            for data_image in images:
                image_name = f"{uuid.uuid4()}.jpg"
                image_names.append(image_name)
                image_path = os.path.join(IMAGE_CACHE_DIR, image_name)
                with open(image_path, "wb") as img_file:
                    img_file.write(base64.b64decode(data_image.split(",")[1]))
                    new_message["content"].append(
                        {"type": "image_url", "image_url": {"url": data_image}}
                    )
            if images and enable_image_generation:
                __messages__.insert(-1, new_message)
            event_description = "R code executed successfully"
        except Exception as e:
            output = str(e)
            event_description = f"Error executing R code: {e}"
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

            images_as_md = [
                f"![{im.strip()}](/cache/image/generations/{im.strip()})"
                for im in image_names
            ]
            await __event_emitter__(
                {
                    "type": "message",
                    "data": {
                        "content": event_data_template.format(
                            code=code,
                            output=output,
                            ts=datetime.datetime.now().isoformat(),
                            images_as_md="\n".join(images_as_md),
                        )
                    },
                }
            )

        return retval
