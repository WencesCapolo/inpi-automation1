# XLS Sheet Reader

This Python script allows you to read an XLS file from a URL and search for specific sheets named "OPOSICIONES" and "VISTAS".

## Requirements

- Python 3.x
- Required packages are listed in `requirements.txt`

## Installation

1. Clone this repository
2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the script:
```bash
python read_xls.py
```

When prompted, enter the URL of the XLS file you want to analyze. The script will:
1. Download the file from the provided URL
2. Search for sheets named "OPOSICIONES" and "VISTAS"
3. If found, display a preview of the contents of these sheets

## Error Handling

The script includes error handling for:
- Invalid URLs
- Network connection issues
- Invalid Excel file formats
- Missing sheets

If any error occurs, an appropriate error message will be displayed. 