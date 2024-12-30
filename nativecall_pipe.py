"""
title: Native Call Pipe
author: smonux
author_url:  https://github.com/smonux/open-webui-docker-execution
version: 0.0.1

This OpenWebUI Function Pipe allows to use the native calling mechanism
in models which support through the API ("tools" parameter).

Initally a Pull Request to OpenAI adapted to work as a function. It uses
OpenWebUI internal methods which may break it. Tested with 0.5.2.


"""

import os
from typing import AsyncGenerator, Awaitable, Callable, Optional, Protocol
from starlette.requests import Request
from starlette.responses import StreamingResponse, JSONResponse, AsyncContentStream
from langchain_core.tools import StructuredTool
from open_webui.main import generate_chat_completions
from open_webui.models.users import UserModel
from pydantic import BaseModel, Field
import inspect
import json
import copy


def extract_json(s: str) -> Optional[dict]:
    try:
        return json.loads(s[s.find("{") : s.rfind("}") + 1])
    except Exception:
        return None


def fill_with_delta(fcall_dict: dict, delta: dict) -> None:
    if fcall_dict == {}:
        fcall_dict.update(
            {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }
        )
    if "delta" not in delta.get("choices", [{}])[0]:
        return
    j = delta["choices"][0].get("delta", {}).get("tool_calls", [{}])[0]
    if "id" in j:
        fcall_dict["id"] += j.get("id", "") or ""
    if "function" in j:
        fcall_dict["function"]["name"] += j["function"].get("name", "")
        fcall_dict["function"]["arguments"] += j["function"].get("arguments", "")


def update_body_request(request: Request, body: dict) -> None:
    modified_body_bytes = json.dumps(body).encode("utf-8")
    # Replace the request body with the modified one
    request._body = modified_body_bytes
    # Set custom header to ensure content-length matches new body length
    request.headers.__dict__["_list"] = [
        (b"content-length", str(len(modified_body_bytes)).encode("utf-8")),
        *[(k, v) for k, v in request.headers.raw if k.lower() != b"content-length"],
    ]
    return None


async def process_tool_calls(
    tool_calls: list,
    event_emitter: Callable[[dict], Awaitable[None]] | None,
    messages: list,
    tools: dict,
) -> None:
    for tool_call in tool_calls:
        # fix for cohere
        if "index" in tool_call:
            del tool_call["index"]

        tool_function_name = tool_call["function"]["name"]
        tool_function_params = {}
        args = tool_call["function"]["arguments"]
        if isinstance(args, str):
            tool_function_params = json.loads(args) if args else {}
        elif isinstance(args, dict):
            tool_function_params = args
        else:
            raise Exception(f"Unexpected arguments {args=}")

        try:
            func = tools[tool_function_name]["callable"]
            all_params = tool_function_params
            if "__messages__" in inspect.signature(func).parameters:
                all_params = tool_function_params | {"__messages__": messages}

            tool_output = await func(**all_params)
        except Exception as e:
            tool_output = str(e)

        if tools.get(tool_function_name, {}).get("citation", False):
            await event_emitter(
                {
                    "type": "source",
                    "data": {
                        "source": {
                            "name": f"TOOL:{tools[tool_function_name]['toolkit_id']}/{tool_function_name}"
                        },
                        "document": [tool_output],
                        "metadata": [{"source": tool_function_name}],
                    },
                }
            )

        # Append the tool output to the messages
        # Ollama can't see the function name so we add context
        # It consumes some tokens but it's helpful also for OpenAI models
        content = f"""
        ##{tool_function_name=}
        ##{tool_function_params=}
        ##tool_output=
        {tool_output}
        """

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "name": tool_function_name,
                "content": content,
            }
        )


async def handle_streaming_response(
    request: Request,
    response: StreamingResponse,
    tools: dict,
    user: UserModel,
    is_ollama: bool,
    event_emitter: Callable[[dict], Awaitable[None]] | None,
):
    body = json.loads(request._body)
    is_openai = not is_ollama

    def wrap_item(item):
        return f"data: {item}\n\n" if is_openai else f"{item}\n"

    def is_tool_call(full_msg: Optional[dict]):
        if full_msg is None:
            return False

        try:
            if "tool_calls" in full_msg["message"]:
                return True
        except (IndexError, KeyError):
            pass

        try:
            if "tool_calls" in full_msg["choices"][0]["delta"]:
                return True
        except (IndexError, KeyError):
            pass
        return False

    def extract_content(full_msg: dict):
        content = ""
        try:
            content = full_msg["choices"][0]["delta"]["content"]
        except (IndexError, KeyError, TypeError):
            pass

        try:
            content = full_msg["message"]["content"]
        except (IndexError, KeyError, TypeError):
            pass
        return content if content else ""

    def is_end_of_stream(full_msg: str):
        if full_msg == "data: [DONE]\n":
            return True

        msg_json = extract_json(full_msg)

        if msg_json is None:
            return False

        if is_tool_call(msg_json):
            return False

        if "done" in msg_json and msg_json["done"]:
            return True

        return False

    async def stream_wrapper(
        original_generator: AsyncContentStream, data_items: list[dict]
    ):
        for item in data_items:
            yield wrap_item(json.dumps(item))

        citations = []
        generator = original_generator
        try:
            buffered_content = ""
            while True:
                peek = await anext(generator)
                peek = peek.decode("utf-8") if isinstance(peek, bytes) else peek
                peek_json = extract_json(peek) or {}

                """
                if len(citations) > 0 and is_end_of_stream(peek):
                    yield wrap_item(json.dumps({"sources": citations}))
                """

                if is_ollama and is_end_of_stream(peek):
                    # ollama #5796 mixes content and end of stream mark which messes up
                    # the UI. We create a spurious message to make it work.
                    content_msg = {
                        k: peek_json[k] for k in ["model", "created_at", "message"]
                    }
                    content_msg["done"] = False
                    yield wrap_item(json.dumps(content_msg))

                if not is_tool_call(peek_json):
                    content = extract_content(peek_json)
                    buffered_content += content
                    yield peek
                    continue

                # We reached a tool call
                tool_calls = []

                if is_openai:
                    tool_calls.append({})
                    current_index = 0
                    fill_with_delta(tool_calls[current_index], peek_json)

                    async for data in generator:
                        delta = extract_json(
                            data.decode("utf-8") if isinstance(data, bytes) else data
                        )

                        if (
                            delta is None
                            or "choices" not in delta
                            or "tool_calls" not in delta["choices"][0]["delta"]
                            or delta["choices"][0].get("finish_reason", None)
                            is not None
                        ):
                            continue

                        i = delta["choices"][0]["delta"]["tool_calls"][0]["index"]
                        if i != current_index:
                            tool_calls.append({})
                            current_index = i

                        fill_with_delta(tool_calls[i], delta)
                else:
                    tool_calls = peek_json["message"]["tool_calls"]
                    async for data in generator:
                        peek_json = (
                            extract_json(
                                data.decode("utf-8")
                                if isinstance(data, bytes)
                                else data
                            )
                            or {}
                        )
                        if "tool_calls" in peek_json["message"]:
                            tool_calls.extend(peek_json["message"]["tool_calls"])

                print(f"tools to call { [ t['function']['name'] for t in tool_calls] }")

                if buffered_content.strip():
                    body["messages"].append(
                        {
                            "role": "assistant",
                            "content": buffered_content,
                        }
                    )
                    buffered_content = ""

                tool_calls: list = (
                    extract_json(tool_calls)
                    if isinstance(tool_calls, str)
                    else tool_calls
                )
                body["messages"].append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": tool_calls,
                    }
                )

                await process_tool_calls(
                    tool_calls=tool_calls,
                    event_emitter=event_emitter,
                    messages=body["messages"],
                    tools=tools,
                )
                # Make another request to the model with the updated context
                # print("calling the model again with tool output included")
                update_body_request(request, body)
                response = await generate_chat_completions(
                    request=request,
                    form_data=body,
                    user=user,
                )
                if isinstance(response, StreamingResponse):
                    # body_iterator here does not have __anext_() so it has to be done this way
                    generator = (x async for x in response.body_iterator)
                else:
                    raise Exception(f"{response=} is not a StreamingResponse")

        except StopAsyncIteration:
            pass
        except Exception as e:
            print(f"Error: {e}")
            raise e

    return StreamingResponse(
        stream_wrapper(response.body_iterator, []),
        headers=dict(response.headers),
    )


async def handle_nonstreaming_response(
    request: Request,
    response: dict,
    tools: dict,
    user: UserModel,
    is_ollama: bool,
    event_emitter: Callable[[dict], Awaitable[None]] | None,
) -> str:

    response_dict = response
    body = json.loads(request._body)
    is_openai = not is_ollama

    def get_message_ollama(d: dict) -> dict:
        return d.get("message", {})

    def get_message_openai(d: dict) -> dict:
        return d.get("choices", [{}])[0].get("message", {})

    get_message = get_message_ollama if is_ollama else get_message_openai

    citations = []
    content = ""

    while "tool_calls" in get_message(response_dict):
        message = get_message(response_dict)
        tool_calls = []
        content += message.get("content", "") or ""
        tool_calls = message.get("tool_calls", [])
        body["messages"].append(message)

        await process_tool_calls(
            tool_calls=tool_calls,
            event_emitter=event_emitter,
            messages=body["messages"],
            tools=tools,
        )

        model_id = body["model"].split(".", 1)[-1]
        body["model"] = model_id
        body["tool_ids"] = []
        # Make another request to the model with the updated context
        update_body_request(request, body)
        print("HHHH", body["model"])
        untyped_response = await generate_chat_completions(
            form_data=body, user=user, request=request
        )
        print(f"{untyped_response=}")
        if not isinstance(untyped_response, dict):
            raise Exception(
                f"Expecting dict from generate_chat_completions got {untyped_response=}"
            )
        response_dict = untyped_response

    message = get_message(response_dict)
    content += " " + message.get("content", "")

    return content


class Pipe:
    class Valves(BaseModel):
        MODEL_PREFIX: str = Field(
            default="nativecall", description="Prefix before model ID"
        )
        OPENAI_API_ENABLED_MODELS: str = Field(
            default="gpt-4o,gpt-4o-mini",
            description="Enabled models, comma-separated.",
        )

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves(
            **{k: os.getenv(k, v.default) for k, v in self.Valves.model_fields.items()}
        )
        print(f"{self.valves=}")

    def pipes(self) -> list[dict[str, str]]:
        # TODO:  fix this
        models = [m.strip() for m in self.valves.OPENAI_API_ENABLED_MODELS.split(",")]
        # models.extend([m.strip() for m in self.valves.OLLAMA_ENABLED_MODELS.split(",")])
        return [{"id": m, "name": f"{self.valves.MODEL_PREFIX}/{m}"} for m in models]

    async def pipe(
        self,
        body: dict,
        __user__: dict | None,
        __task__: str | None,
        __tools__: dict[str, dict] | None,
        __event_emitter__: Callable[[dict], Awaitable[None]] | None,
    ) -> AsyncGenerator | str:
        try:
            # HACK: Ignoring "tool call prompts" looking at the prompt. May break
            if body["messages"][0]["content"].startswith("Available Tools"):
                return ""
        except Exception:
            pass
        """
        print(
            "-->body\n",
            body,
            "\n--user--\n",
            __user__,
            "\n--tools--\n",
            __tools__,
            "\n--event-emitter\n",
            __event_emitter__,
        )
        """

        if __tools__ is None:
            __tools__ = {}

        # HACK: Get the variables from calling functions
        # using reflection/inspection
        caller_frame = inspect.currentframe()
        request = None
        for _ in range(10):
            if caller_frame is None or caller_frame.f_back is None:
                continue
            caller_locals = caller_frame.f_back.f_locals
            if "request" in caller_locals and isinstance(
                caller_locals["request"], Request
            ):
                request = caller_locals["request"]
                continue
            else:
                caller_frame = caller_frame.f_back

        caller_frame = inspect.currentframe()
        user = None
        for _ in range(10):
            if caller_frame is None or caller_frame.f_back is None:
                continue
            caller_locals = caller_frame.f_back.f_locals
            if "user" in caller_locals:
                user = caller_locals["user"]
                continue
            else:
                caller_frame = caller_frame.f_back

        # TODO: assert over request and user
        tools = []
        for t in __tools__.values():
            # handling str -> string or Openai.com complains
            # Invalid schema for function '<function>': 'str' is not valid under any of the given schemas.
            spec = copy.deepcopy(t["spec"])
            for p in spec["parameters"].get("properties", {}).values():
                if p["type"] == "str":
                    p["type"] = "string"
            tools.append({"type": "function", "function": spec})

        if tools:
            body["tools"] = tools

        model_id = body["model"].split(".", 1)[-1]
        body["model"] = model_id
        body["tool_ids"] = []

        first_response = await generate_chat_completions(
            request=request, form_data=body, user=user
        )
        if not tools:
            return first_response

        is_ollama = False
        if not body["stream"]:
            # FIXME: : returning content duplicates the ouput (why?)
            content = await handle_nonstreaming_response(
                request=request,
                response=first_response,
                tools=__tools__,
                user=user,
                is_ollama=is_ollama,
                event_emitter=__event_emitter__,
            )
            return ""
        else:
            content = await handle_streaming_response(
                request=request,
                response=first_response,
                tools=__tools__,
                user=user,
                is_ollama=is_ollama,
                event_emitter=__event_emitter__,
            )
            return content
