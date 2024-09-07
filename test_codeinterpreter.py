import unittest
import asyncio
from codeinterpreter import Tools
import re
from unittest.mock import Mock, AsyncMock

class TestCodeInterpreter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tools = Tools()
        self.tools.valves.CODE_INTERPRETER_TIMEOUT = 2  # Set timeout to 2 seconds for testing

    async def test_run_python_code_with_timeout(self):
        code = """
import time
time.sleep(3)  # Sleep for 3 seconds to exceed the 2-second timeout
"""
        event_emitter = AsyncMock()
        result = await self.tools.run_python_code(code, event_emitter)
        self.assertIn("Error: Timeout", result)

    async def test_run_python_code_prints_2_plus_2(self):
        code = """
print(2 + 2)
"""
        event_emitter = Mock()
        result = await self.tools.run_python_code(code, event_emitter)
        self.assertIn("4", result)

if __name__ == '__main__':
    unittest.main()
