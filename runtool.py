import asyncio
import sys
from dockerinterpreter import Tools

async def _main():
    tool = Tools()
    print(tool.run_python_code.__doc__)
    code = """
import time
import os
time.sleep(0.5)
print("Hello ---> world")

print(os.listdir())
"""
    async def _dummy_emitter(event):
        print(f"Event: {event}", file=sys.stderr) 
    retval = await tool.run_python_code(code, _dummy_emitter)
    print(retval)

if __name__ == '__main__':
    asyncio.run(_main())
