import unittest
from codeinterpreter import Tools

class TestCodeInterpreter(unittest.TestCase):
    def setUp(self):
        self.tools = Tools()

    def test_run_python_code_with_matplotlib(self):
        code = """
import matplotlib.pyplot as plt
plt.plot([1, 2, 3, 4])
plt.ylabel('some numbers')
plt.savefig('simple_plot.png')
"""
        result = self.tools.run_python_code(code, lambda x: None)
        self.assertIn("simple_plot.png", result)

if __name__ == '__main__':
    unittest.main()
