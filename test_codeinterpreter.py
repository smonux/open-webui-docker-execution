import unittest
import asyncio
from codeinterpreter import Tools
import re

class TestCodeInterpreter(unittest.TestCase):
    def setUp(self):
        self.tools = Tools()
        self.tools.valves.CODE_INTERPRETER_TIMEOUT = 2  # Set timeout to 2 seconds for testing

    async def test_run_python_code_with_timeout(self):
        code = """
import time
time.sleep(3)  # Sleep for 3 seconds to exceed the 2-second timeout
"""
        result = await self.tools.run_python_code(code, lambda x: asyncio.ensure_future(x({})))
        self.assertIn("Error: Timeout", result)

if __name__ == '__main__':
    unittest.main()
