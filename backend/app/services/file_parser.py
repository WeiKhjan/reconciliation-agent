"""
File parsing service for CSV, Excel, and PDF files.
"""
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class FileParser:
    """Handles parsing of CSV, Excel, and PDF files."""

    SUPPORTED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.pdf'}
    COMMON_ENCODINGS = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']

    def parse(
        self,
        file_content: bytes,
        filename: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Parse file content and return DataFrame with metadata.

        Args:
            file_content: Raw file bytes
            filename: Original filename

        Returns:
            Tuple of (DataFrame, metadata_dict)
        """
        ext = Path(filename).suffix.lower()

        if ext == '.csv':
            return self._parse_csv(file_content, filename)
        elif ext in {'.xlsx', '.xls'}:
            return self._parse_excel(file_content, filename)
        elif ext == '.pdf':
            return self._parse_pdf(file_content, filename)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _parse_csv(
        self,
        file_content: bytes,
        filename: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse CSV with automatic encoding detection."""
        last_error = None

        for encoding in self.COMMON_ENCODINGS:
            try:
                df = pd.read_csv(
                    BytesIO(file_content),
                    encoding=encoding,
                    on_bad_lines='warn'
                )
                # Clean column names
                df.columns = df.columns.str.strip()

                metadata = {
                    "filename": filename,
                    "file_type": "csv",
                    "encoding": encoding,
                    "rows": len(df),
                    "columns": df.columns.tolist(),
                    "size_bytes": len(file_content),
                    "parser_used": "pandas"
                }
                logger.info(f"Parsed CSV {filename} with encoding {encoding}")
                return df, metadata
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to parse CSV with encoding {encoding}: {e}")
                continue

        raise ValueError(f"Could not parse CSV file: {last_error}")

    def _parse_excel(
        self,
        file_content: bytes,
        filename: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse Excel file, handling multiple sheets."""
        try:
            xls = pd.ExcelFile(BytesIO(file_content))
            sheet_names = xls.sheet_names

            if len(sheet_names) == 1:
                df = pd.read_excel(BytesIO(file_content))
                active_sheet = sheet_names[0]
            else:
                # Use first sheet by default
                df = pd.read_excel(BytesIO(file_content), sheet_name=0)
                active_sheet = sheet_names[0]
                logger.info(f"Multiple sheets detected in {filename}, using first sheet: {active_sheet}")

            # Clean column names
            df.columns = df.columns.str.strip()

            metadata = {
                "filename": filename,
                "file_type": "excel",
                "rows": len(df),
                "columns": df.columns.tolist(),
                "size_bytes": len(file_content),
                "sheets": sheet_names,
                "active_sheet": active_sheet,
                "parser_used": "pandas"
            }

            return df, metadata

        except Exception as e:
            logger.error(f"Failed to parse Excel file {filename}: {e}")
            raise ValueError(f"Could not parse Excel file: {e}")

    def _parse_pdf(
        self,
        file_content: bytes,
        filename: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse PDF tables using pdfplumber with fallbacks."""
        # Try pdfplumber first
        try:
            return self._parse_pdf_pdfplumber(file_content, filename)
        except Exception as e:
            logger.warning(f"pdfplumber failed for {filename}: {e}")

        # Try PyMuPDF as fallback for text extraction
        try:
            return self._parse_pdf_pymupdf(file_content, filename)
        except Exception as e:
            logger.warning(f"PyMuPDF failed for {filename}: {e}")

        raise ValueError("Could not extract tables from PDF. Please convert to CSV or Excel.")

    def _parse_pdf_pdfplumber(
        self,
        file_content: bytes,
        filename: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse PDF using pdfplumber."""
        import pdfplumber

        all_tables = []
        pages_processed = 0

        with pdfplumber.open(BytesIO(file_content)) as pdf:
            pages_processed = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        # First row as headers
                        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(table[0])]
                        df_table = pd.DataFrame(table[1:], columns=headers)
                        df_table['_source_page'] = page_num + 1
                        all_tables.append(df_table)

        if not all_tables:
            raise ValueError("No tables found in PDF")

        # Combine all tables
        df = pd.concat(all_tables, ignore_index=True)

        metadata = {
            "filename": filename,
            "file_type": "pdf",
            "rows": len(df),
            "columns": df.columns.tolist(),
            "size_bytes": len(file_content),
            "pages_processed": pages_processed,
            "tables_found": len(all_tables),
            "parser_used": "pdfplumber"
        }

        return df, metadata

    def _parse_pdf_pymupdf(
        self,
        file_content: bytes,
        filename: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Fallback PDF parser using PyMuPDF for text extraction."""
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_content, filetype="pdf")
        all_text = []

        for page in doc:
            text = page.get_text()
            all_text.append(text)

        doc.close()

        # Try to parse text as tabular data
        full_text = "\n".join(all_text)
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]

        if not lines:
            raise ValueError("No text content found in PDF")

        # Attempt to detect delimiter and parse
        # This is a basic fallback - may not work for all PDFs
        data = []
        for line in lines:
            # Try common delimiters
            for delimiter in ['\t', '|', ',', '  ']:
                parts = [p.strip() for p in line.split(delimiter) if p.strip()]
                if len(parts) > 1:
                    data.append(parts)
                    break
            else:
                data.append([line])

        if not data:
            raise ValueError("Could not parse PDF content as tabular data")

        # Use first row as headers if it looks like headers
        max_cols = max(len(row) for row in data)
        headers = [f"col_{i}" for i in range(max_cols)]

        # Pad rows to match max columns
        padded_data = []
        for row in data:
            padded_row = row + [''] * (max_cols - len(row))
            padded_data.append(padded_row)

        df = pd.DataFrame(padded_data, columns=headers)

        metadata = {
            "filename": filename,
            "file_type": "pdf",
            "rows": len(df),
            "columns": df.columns.tolist(),
            "size_bytes": len(file_content),
            "pages_processed": len(all_text),
            "parser_used": "pymupdf",
            "note": "Text extraction fallback - may need manual cleanup"
        }

        return df, metadata

    def get_schema(self, df: pd.DataFrame) -> Dict[str, str]:
        """Extract column names and inferred types."""
        return {col: str(df[col].dtype) for col in df.columns}

    def get_preview(
        self,
        df: pd.DataFrame,
        rows: int = 10
    ) -> Dict[str, Any]:
        """Generate preview data for a DataFrame."""
        return {
            "columns": df.columns.tolist(),
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
            "sample_rows": df.head(rows).fillna("").to_dict('records'),
            "total_rows": len(df)
        }

    def to_markdown_preview(
        self,
        df: pd.DataFrame,
        rows: int = 10
    ) -> str:
        """Generate markdown preview of DataFrame for LLM context."""
        return df.head(rows).to_markdown(index=False)


# Global parser instance
file_parser = FileParser()
