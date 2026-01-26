import csv
import argparse
import os
import sys

def extract_columns(input_path, column_indices, output_path=None):
    """
    Extracts specified columns from a TSV file and saves them to a new TSV file.

    Args:
        input_path (str): Path to the input TSV file.
        column_indices (list of int): List of column indices to extract.
        output_path (str, optional): Path to the output TSV file. 
            Defaults to <input_name>_core.tsv if not provided.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_core{ext}"

    try:
        with open(input_path, mode='r', encoding='utf-8') as infile:
            reader = csv.reader(infile, delimiter='\t')
            
            with open(output_path, mode='w', encoding='utf-8', newline='') as outfile:
                writer = csv.writer(outfile, delimiter='\t')
                
                for row in reader:
                    if not row:
                        continue
                    
                    try:
                        extracted_row = [row[i] for i in column_indices]
                        writer.writerow(extracted_row)
                    except IndexError:
                        # Optionally handle rows with fewer columns than requested
                        print(f"Warning: Row has fewer than {max(column_indices) + 1} columns. Skipping row.")
                        continue

        print(f"Successfully extracted columns to '{output_path}'")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Extract specific columns from a TSV file.")
    parser.add_argument("input", help="Path to the input TSV file.")
    parser.add_argument("columns", help="Comma-separated list of column indices to extract (e.g., '0,2,3').")
    parser.add_argument("-o", "--output", help="Path to the output TSV file (optional).")

    args = parser.parse_args()

    try:
        column_indices = [int(i.strip()) for i in args.columns.split(',')]
    except ValueError:
        print("Error: Columns must be a comma-separated list of integers.")
        sys.exit(1)

    extract_columns(args.input, column_indices, args.output)

if __name__ == "__main__":
    main()
