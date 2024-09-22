import unittest
import asyncio
from dockerinterpreter import Tools
from unittest.mock import AsyncMock

class TestCodeInterpreter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tools = Tools()
        self.tools.valves.CODE_INTERPRETER_TIMEOUT = 2  # Set timeout to 2 seconds for testing
        self.tools.valves.SHARED_FILES_PATH = "/tmp" 

    async def test_run_python_code_with_timeout(self):
        code = """
import time
time.sleep(3)  # Sleep for 3 seconds to exceed the 2-second timeout
print("This should not be printed due to timeout")
"""
        event_emitter = AsyncMock()
        result = await self.tools.run_python_code(code, event_emitter)
        
        # Check if the timeout error is present in the result
        self.assertIn("Error: Timeout", result)
        
        # Verify that the print statement wasn't executed
        self.assertNotIn("This should not be printed due to timeout", result)
        
        # Check if the event emitter was called with the correct status
        event_emitter.assert_any_call({
            "type": "status",
            "data": {
                "description": "Executing Python code",
                "status": "in_progress",
                "done": False,
            },
        })
        
        # The last call should be the error status
        event_emitter.assert_called_with({
            "type": "status",
            "data": {
                "description": "Error executing Python code: Timeout",
                "status": "complete",
                "done": True,
            },
        })



if __name__ == '__main__':
    unittest.main()
