import unittest
import asyncio
from codeinterpreter import Tools

class TestCodeInterpreter(unittest.TestCase):
    def setUp(self):
        self.tools = Tools()

    async def test_run_python_code_with_calculation(self):
        code = """
result = 2 + 2
print(f'The result of the calculation is: {result}')
"""
        result = await self.tools.run_python_code(code, lambda x: asyncio.ensure_future(x({})))
        self.assertIn("The result of the calculation is: 4", result)

if __name__ == '__main__':
    unittest.main()
