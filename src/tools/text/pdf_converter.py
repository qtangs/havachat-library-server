import json
import argparse
import os
import sys
from pathlib import Path
from docling.document_converter import DocumentConverter
import pandas as pd

def convert_pdf(input_path, config_str, output_path=None):
    """
    Converts a PDF file to Markdown, TXT, or Word format using Docling.
    
    Args:
        input_path (str): Path to the input PDF file.
        config_str (str): JSON string with config fields.
        output_path (str, optional): Path to the output file.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)

    # Parse config
    try:
        config = json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON config: {e}")
        sys.exit(1)

    output_format = config.get("format", "markdown").lower()
    extract_tables = config.get("extractTables", True)
    page_range_str = config.get("pageRange") # e.g. "1-5" or "1"
    
    # Process page range
    page_range = None
    if page_range_str:
        try:
            if "-" in str(page_range_str):
                start, end = map(int, str(page_range_str).split("-"))
                page_range = [start, end]
            else:
                page_range = [int(page_range_str), int(page_range_str)]
        except ValueError:
            print(f"Warning: Invalid page range format '{page_range_str}'. Ignoring.")

    # Determine extension
    ext_map = {
        "markdown": ".md",
        "txt": ".txt",
        "word": ".docx"
    }
    
    if output_format not in ext_map:
        print(f"Error: Unsupported format '{output_format}'. Supported formats: markdown, txt, word")
        sys.exit(1)

    target_ext = ext_map[output_format]

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}{'-' + page_range_str if page_range_str else ''}{target_ext}"

    print(f"Converting '{input_path}' (Pages: {page_range_str if page_range_str else 'All'}) to '{output_format}' ({output_path})...")

    try:
        converter = DocumentConverter()
        # Pass page_range to convert method
        result = converter.convert(input_path, page_range=page_range)
        
        content = ""
        if output_format == "markdown":
            content = result.document.export_to_markdown()
        elif output_format == "txt":
            # Markdown is often the best plain text representation from Docling
            # but we can try to strip some markdown if needed. 
            # For now, we'll provide the markdown content as txt.
            content = result.document.export_to_markdown()
        elif output_format == "word":
            # Docling doesn't natively export to .docx yet.
            # We export to HTML which Word can open.
            content = result.document.export_to_html()
            print("Note: Word output is exported as HTML content saved as .docx for compatibility.")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Successfully converted to '{output_path}'")

        # Extract tables if requested
        if extract_tables and result.document.tables:
            print("Extracting tables...")
            output_dir = Path(os.path.dirname(os.path.abspath(output_path)))
            doc_filename = Path(output_path).stem
            
            for table_ix, table in enumerate(result.document.tables):
                # Export to dataframe
                table_df = table.export_to_dataframe(doc=result.document)
                
                # Forward fill cells that spread across multiple rows (assume empty string means merged)
                # We replace empty strings with None to allow ffill, then fill remaining cells (if any) with empty string
                table_df = table_df.replace("", None).ffill().fillna("")

                # Save as CSV
                element_csv_filename = output_dir / f"{doc_filename}-table{'-' + page_range_str if page_range_str else ''}-{table_ix + 1}.csv"
                print(f"Saving CSV table to {element_csv_filename}")
                table_df.to_csv(element_csv_filename, index=False)
                
                # # Save as HTML
                # element_html_filename = output_dir / f"{doc_filename}-table{'-' + page_range_str if page_range_str else ''}-{table_ix + 1}.html"
                # print(f"Saving HTML table to {element_html_filename}")
                # with element_html_filename.open("w", encoding="utf-8") as fp:
                #     fp.write(table.export_to_html(doc=result.document))

    except Exception as e:
        print(f"An error occurred during conversion: {e}")
        # Print stack trace
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Convert PDF to other formats using Docling.")
    parser.add_argument("input", help="Path to the input PDF file.")
    parser.add_argument("config", help="JSON config: '{\"format\": \"markdown|txt|word\", \"extractTables\": bool}'")
    parser.add_argument("-o", "--output", help="Path to the output file (optional).")

    args = parser.parse_args()

    convert_pdf(args.input, args.config, args.output)

if __name__ == "__main__":
    main()
