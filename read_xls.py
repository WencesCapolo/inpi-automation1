import pandas as pd
import sys
import os
import json
from pathlib import Path
from datetime import datetime

def process_sheet(df, sheet_name):
    """
    Process a single sheet and extract rows where first column is 'Part.'
    """
    try:
        print(f"\nDebug: Starting to process sheet {sheet_name}")
        # Find the row index where 'Agente' appears
        agente_idx = df.iloc[:, 0][df.iloc[:, 0] == 'Agente'].index[0]
        print(f"Debug: Found 'Agente' at row {agente_idx}")
        
        # Use the row after 'Agente' as header
        df.columns = df.iloc[agente_idx, :]
        
        # Get data after the header row
        data_df = df.iloc[agente_idx + 1:].copy()
        data_df.columns = ['Agente' if pd.isna(col) else str(col).strip() for col in data_df.columns]
        
        print(f"Debug: Columns after cleanup: {list(data_df.columns)}")
        
        # Filter rows where Agente column equals 'Part.'
        part_rows = data_df[data_df['Agente'] == 'Part.'].copy()
        print(f"Debug: Found {len(part_rows)} rows with Part.")
        
        # Convert to dictionary format
        rows_data = []
        for idx, row in part_rows.iterrows():
            row_dict = {}
            for col in data_df.columns:
                val = row[col]
                if pd.isna(val):
                    row_dict[col] = None
                else:
                    # Convert any non-string types to string
                    row_dict[col] = str(val).strip()
            row_dict['origen'] = sheet_name
            rows_data.append(row_dict)
            
            # Print first row as debug
            if len(rows_data) == 1:
                print(f"Debug: First row example: {json.dumps(row_dict, ensure_ascii=False)}")
        
        return rows_data
    
    except Exception as e:
        print(f"Error processing sheet {sheet_name}: {str(e)}")
        import traceback
        print(f"Debug: Full error traceback:\n{traceback.format_exc()}")
        return []

def analyze_xls_file(file_path):
    """
    Analyze the XLS file and extract relevant rows
    """
    try:
        print(f"\nAnalyzing file: {file_path}")
        
        # Read the Excel file with xlrd engine for .xls files
        excel = pd.ExcelFile(file_path, engine='xlrd')
        sheet_names = excel.sheet_names
        print(f"All sheets found: {sheet_names}")
        
        # Look for our target sheets
        target_sheets = ["OPOSICIONES", "VISTAS"]
        all_part_rows = []
        
        # Create metadata
        metadata = {
            "source_file": os.path.basename(file_path),
            "processing_date": datetime.now().isoformat(),
            "sheets_processed": []
        }
        
        for sheet in target_sheets:
            # Try to find the sheet (case sensitive and insensitive)
            matching_sheets = [s for s in sheet_names if s.upper() == sheet.upper()]
            
            if matching_sheets:
                actual_sheet_name = matching_sheets[0]
                print(f"\nProcessing sheet: {actual_sheet_name}")
                
                # Read the sheet
                df = pd.read_excel(excel, sheet_name=actual_sheet_name)
                print(f"Debug: Sheet {actual_sheet_name} has {len(df)} rows")
                
                # Process the sheet and get Part. rows
                sheet_rows = process_sheet(df, actual_sheet_name)
                if sheet_rows:
                    all_part_rows.extend(sheet_rows)
                    print(f"Found {len(sheet_rows)} rows with Agente = 'Part.' in {actual_sheet_name}")
                    metadata["sheets_processed"].append({
                        "name": actual_sheet_name,
                        "rows_found": len(sheet_rows)
                    })
            else:
                print(f"\nWarning: No sheet found matching '{sheet}'")
        
        if all_part_rows:
            # Prepare final JSON structure
            output_data = {
                "metadata": metadata,
                "data": all_part_rows
            }
            
            # Debug: Print first row of data
            print(f"\nDebug: First row of final data: {json.dumps(output_data['data'][0], ensure_ascii=False)}")
            
            # Save to JSON with error handling
            output_file = 'part_data.json'
            try:
                json_str = json.dumps(output_data, ensure_ascii=False, indent=2)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                print(f"\nSaved {len(all_part_rows)} total rows to {output_file}")
            except Exception as e:
                print(f"Debug: Error saving JSON: {str(e)}")
                import traceback
                print(f"Debug: Full error traceback:\n{traceback.format_exc()}")
            
            print("\nSummary of found rows by sheet:")
            for sheet_info in metadata["sheets_processed"]:
                print(f"{sheet_info['name']}: {sheet_info['rows_found']} rows")
        else:
            print("\nNo rows with Agente = 'Part.' were found")
        
    except Exception as e:
        print(f"Error analyzing Excel file: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Debug: Full error traceback:\n{traceback.format_exc()}")
        sys.exit(1)

def main():
    # Input file
    input_file = "5877_3_.xls"
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found!")
        sys.exit(1)
    
    try:
        # Analyze XLS directly
        analyze_xls_file(input_file)
        
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Debug: Full error traceback:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main() 