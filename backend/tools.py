import subprocess
import tempfile
import os
from crewai.tools import tool

@tool("Python Code Executor")
def execute_python_code(code: str) -> str:
    """
    Executes the given Python code in a secure sandbox and returns the terminal output or error.
    Useful for QA testing to verify if the generated code functions correctly.
    """
    try:
        # Create a temporary .py file to store the generated code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            # Clean up markdown formatting if the LLM includes it
            clean_code = code.strip().removeprefix("```python").removesuffix("```").strip()
            temp_file.write(clean_code)
            temp_file_path = temp_file.name

        # Execute the temporary file using subprocess with a 5-second timeout limit
        result = subprocess.run(
            ['python', temp_file_path],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Delete the temporary file after execution to prevent storage clutter
        os.remove(temp_file_path)

        # Evaluate the execution result and return feedback to the agent
        if result.returncode == 0:
            return f"Execution Successful! Output:\n{result.stdout}"
        else:
            return f"Execution Failed! Error Traceback:\n{result.stderr}"

    except subprocess.TimeoutExpired:
        # Ensure the file is safely deleted even if a timeout occurs
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return "Execution Failed: Code took too long to run (Timeout Exceeded). Check for infinite loops."
        
    except Exception as e:
        return f"Execution System Failed: {str(e)}"