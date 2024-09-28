# DockerInterpreter Tool

## Description & usage

This is an openwebui tool that can run arbitrary Python code (other languages 
might be added in the future). 

It's based/inspired by [EtiennePerot/open-webui-code-execution](https://github.com/EtiennePerot/open-webui-code-execution).

The main use case is to couple it with system prompts to implement advanced
assistants like a data analyst, a coding instructor, etc...sadly, OAI 
Tools are bit limited by now, since only can run once by completion,
which doesn't allow the llm to fix coding mistakes or do advanced analysis by itself. I hope this changes in he future. 

It uses Docker tooling for isolating the execution environment. Further security may be achieved by using a non-default Docker engines such as
gVisor's runsc. Although, hopefully, LLM's won't be trying to execute kernel
exploits against us humans and the worst it can happen is a "rm -rf" or the like. That won't do any harm to the host even using docker's default runc engine. 

The simplest method to make it work is to  grant access to the unix socket
that controls docker to oai docker container.

It can be done like this in compose:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

or the equivalent command with bare docker using -v switch.

Note that the container which runs the code can't see the socket, 
only the OAI one.

The docker container is executed with these defaults:

```
mem_limit : "1g"
network_disabled : True
working_dir : /mnt
volumes : 
    - "/tmp:/mnt"
```

These means that you can leave files in /tmp which the llm can use,
 and it can place new ones there too (you will probably will want 
to change it). 

Although it's a Valve, it's not very convenient to use the GUI to
make changes to it. Change the file instead in OAI's built-in editor.

## Valves (configurable parameters)

- CODE_INTERPRETER_TIMEOUT: Self explanatory, the tool kills the executing container if it exceeds the timeout.
- ADDITIONAL_CONTEXT: It allows you to add additional information 
to the llm about how to use the tool.
- DOCKER_SOCKET: Self explanatory, where the socket that controls docker is placed.
- DOCKER_IMAGE: Self explanatory, the default python alpine image is not very useful, you may want to use other,
better equipped image, but **pull it first** or the UI will freeze.
- DOCKER_YAML_OPTIONS: Explained before, check https://docker-py.readthedocs.io/en/stable/containers.html for more options.

## Other files

 - run\*.py : simple tools to check the interpreter without the gui.
 - openwebui-compose-dev.yml : Example docker compose file to run OAI
 - Dockerfile.python.example : more useful python image.



## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
