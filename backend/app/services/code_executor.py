"""
Safe code execution sandbox for reconciliation code.
"""
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List
import logging
import signal
import sys
from contextlib import contextmanager

from app.config import settings

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when code execution times out."""
    pass


class CodeExecutionError(Exception):
    """Raised when code execution fails."""
    pass


class CodeExecutor:
    """Safely executes generated Python code in a sandbox."""

    # Allowed modules for reconciliation code
    ALLOWED_MODULES = {
        'pandas': pd,
        'pd': pd,
        'numpy': np,
        'np': np,
        're': re,
        'datetime': datetime,
        'timedelta': timedelta,
    }

    # Dangerous patterns to block
    BLOCKED_PATTERNS = [
        r'\bimport\s+os\b',
        r'\bimport\s+sys\b',
        r'\bimport\s+subprocess\b',
        r'\bimport\s+shutil\b',
        r'\bimport\s+socket\b',
        r'\bimport\s+requests\b',
        r'\bimport\s+urllib\b',
        r'\bimport\s+http\b',
        r'\b__import__\s*\(',
        r'\beval\s*\(',
        r'\bexec\s*\(',
        r'\bopen\s*\(',
        r'\bfile\s*\(',
        r'\bcompile\s*\(',
        r'\bgetattr\s*\(',
        r'\bsetattr\s*\(',
        r'\bdelattr\s*\(',
        r'\bglobals\s*\(',
        r'\blocals\s*\(',
        r'\b__builtins__\b',
        r'\b__class__\b',
        r'\b__bases__\b',
        r'\b__subclasses__\b',
        r'\b__mro__\b',
    ]

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.CODE_EXECUTION_TIMEOUT

    def validate_code(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate code for dangerous patterns.

        Returns:
            Tuple of (is_valid, error_message)
        """
        for pattern in self.BLOCKED_PATTERNS:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                return False, f"Blocked pattern detected: {match.group()}"
        return True, None

    def clean_code(self, code: str) -> str:
        """Remove markdown code blocks and clean up code."""
        # Remove markdown code blocks
        if "```python" in code:
            parts = code.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0]
        elif "```" in code:
            parts = code.split("```")
            if len(parts) > 1:
                code = parts[1].split("```")[0] if len(parts) > 2 else parts[1]

        return code.strip()

    @contextmanager
    def _timeout_handler(self, seconds: int):
        """Context manager for timeout on Unix systems."""
        def handler(signum, frame):
            raise TimeoutError(f"Code execution timed out after {seconds} seconds")

        # Only use signals on Unix systems
        if sys.platform != 'win32':
            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        else:
            # On Windows, just yield without timeout
            # TODO: Implement Windows-compatible timeout
            yield

    def execute(
        self,
        code: str,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Execute code in sandbox with datasets.

        Args:
            code: Python code to execute
            df_a: First dataset (DataFrame)
            df_b: Second dataset (DataFrame)

        Returns:
            Dict with keys: success, result_df, matched, unmatched_a, unmatched_b, error, match_rate
        """
        # Validate code first
        is_valid, error = self.validate_code(code)
        if not is_valid:
            logger.warning(f"Code validation failed: {error}")
            return {
                "success": False,
                "error": error,
                "match_rate": 0.0
            }

        # Clean code
        code = self.clean_code(code)

        # Prepare execution context with copies of data
        local_scope = {
            'df_a': df_a.copy(),
            'df_b': df_b.copy(),
            'pd': pd,
            'np': np,
            're': re,
            'datetime': datetime,
            'timedelta': timedelta,
        }

        # Safe builtins
        safe_builtins = {
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'sorted': sorted,
            'reversed': reversed,
            'list': list,
            'dict': dict,
            'set': set,
            'tuple': tuple,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'round': round,
            'print': lambda *args, **kwargs: None,  # Suppress prints
            'isinstance': isinstance,
            'hasattr': hasattr,
            'type': type,
            'None': None,
            'True': True,
            'False': False,
        }

        try:
            with self._timeout_handler(self.timeout):
                exec(code, {"__builtins__": safe_builtins}, local_scope)

            # Extract results
            result_df = local_scope.get('result_df')
            unmatched_a = local_scope.get('unmatched_a', pd.DataFrame())
            unmatched_b = local_scope.get('unmatched_b', pd.DataFrame())

            if result_df is None:
                return {
                    "success": False,
                    "error": "Code did not define 'result_df' variable. The matched records must be stored in a variable named 'result_df'.",
                    "match_rate": 0.0
                }

            # Ensure result is a DataFrame
            if not isinstance(result_df, pd.DataFrame):
                return {
                    "success": False,
                    "error": f"'result_df' must be a pandas DataFrame, got {type(result_df).__name__}",
                    "match_rate": 0.0
                }

            # Calculate match statistics
            original_a_count = len(df_a)
            matched_count = len(result_df)
            match_rate = matched_count / original_a_count if original_a_count > 0 else 0

            # Convert DataFrames to records
            matched_records = result_df.fillna("").to_dict('records')

            if isinstance(unmatched_a, pd.DataFrame):
                unmatched_a_records = unmatched_a.fillna("").to_dict('records')
            else:
                unmatched_a_records = []

            if isinstance(unmatched_b, pd.DataFrame):
                unmatched_b_records = unmatched_b.fillna("").to_dict('records')
            else:
                unmatched_b_records = []

            logger.info(f"Code executed successfully. Match rate: {match_rate:.2%}")

            return {
                "success": True,
                "result_df": result_df,
                "matched": matched_records,
                "unmatched_a": unmatched_a_records,
                "unmatched_b": unmatched_b_records,
                "match_rate": match_rate,
                "match_count": matched_count,
                "total_a": original_a_count,
                "total_b": len(df_b),
            }

        except TimeoutError as e:
            logger.error(f"Code execution timed out: {e}")
            return {
                "success": False,
                "error": str(e),
                "match_rate": 0.0
            }
        except SyntaxError as e:
            logger.error(f"Syntax error in code: {e}")
            return {
                "success": False,
                "error": f"SyntaxError: {e.msg} at line {e.lineno}",
                "match_rate": 0.0
            }
        except Exception as e:
            logger.error(f"Code execution failed: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "match_rate": 0.0
            }


# Global executor instance
code_executor = CodeExecutor()
