import asyncio
import sys
from dockerinterpreter import Tools


async def _main():
    tool = Tools()
    tool.valves.DOCKER_IMAGE = "pythonds"
    print(tool.run_python_code.__doc__)
    code = """
import matplotlib.pyplot as plt
import numpy as np

# Create some data
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Create the plot
plt.figure(figsize=(8, 4))
plt.plot(x, y, label='Sine wave')
plt.title('Simple Sine Wave Figure')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.axhline(0, color='black',linewidth=0.5, ls='--')
plt.axvline(0, color='black',linewidth=0.5, ls='--')
plt.grid(color = 'gray', linestyle = '--', linewidth = 0.5)
plt.legend()
plt.show()
"""

    model = "nomodel"
    messages = [{"content": [], "role": "user"}]

    async def _dummy_emitter(event):
        print(f"Event: {event}", file=sys.stderr)

    retval = await tool.run_python_code(code, _dummy_emitter, messages, model)
    print(retval)


if __name__ == "__main__":
    asyncio.run(_main())
