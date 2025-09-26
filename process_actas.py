import requests
import json
import time
import random
import re
import io
import traceback
from PyPDF2 import PdfReader
import streamlit as st

MAX_LOGS = 1_000          # keep last 1 000 entries only
MAX_MSG_LEN = 300         # truncate long messages

def get_session_with_cookies():
    """Initialize session and get cookies from INPI portal"""
    session = requests.Session()
    
    # Get cookies from the homepage (same as get-cookie.py)
    url_inicio = "https://portaltramites.inpi.gob.ar/"
    try:
        response = session.get(url_inicio)
        print(f"Cookies obtained: {len(session.cookies)} cookies")
        return session
    except Exception as e:
        print(f"Error getting cookies: {e}")
        return None

def find_formulario_item(response_data):
    """Find the last valid 'Formulario' item from API response"""
    try:
        if 'rows' not in response_data:
            return None, "No 'rows' found in response"
        
        # First check if any item has "Acompaña Poder" (exact match)
        for item in response_data['rows']:
            indice = item.get('Indice', '')
            if indice == 'Acompaña Poder':
                return None, "Acompaña Poder document found - skipping formulario processing"
        
        # Find all items with Indice = "Formulario" and id_TipoOrigen = 1
        formulario_items = []
        for item in response_data['rows']:
            if (item.get('Indice') == 'Formulario' and 
                item.get('id_TipoOrigen') == 1):
                formulario_items.append(item)
        
        if not formulario_items:
            return None, "No 'Formulario' item found with id_TipoOrigen = 1"
        
        # Take the last one
        last_item = formulario_items[-1]
        
        # Validate required fields
        id_documento_encriptado = last_item.get('id_Documento_encriptado')
        ruta = last_item.get('ruta')
        
        if not id_documento_encriptado:
            return None, "Missing or null 'id_Documento_encriptado'"
        
        if not ruta or '/' not in ruta:
            return None, f"Malformed 'ruta' field: {ruta}"
        
        # Extract filename from ruta
        filename = ruta.split('/')[-1]
        if not filename:
            return None, f"Could not extract filename from ruta: {ruta}"
        
        return {
            'id_documento_encriptado': id_documento_encriptado,
            'filename': filename
        }, None
        
    except Exception as e:
        return None, f"Error parsing response: {e}"

def construct_document_url(id_documento_encriptado, filename):
    """Construct the document URL"""
    return f"https://portaltramites.inpi.gob.ar/Home/edmsxidd?id={id_documento_encriptado}&nombre={filename}"

def download_pdf_with_retry(session, url, max_retries=1):
    """Download PDF with retry logic"""
    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                return response.content, None
            else:
                error_msg = f"HTTP {response.status_code}"
                if attempt < max_retries:
                    continue
                return None, error_msg
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries:
                continue
            return None, error_msg
    
    return None, "Max retries exceeded"

def extract_email_from_pdf(pdf_content):
    """Extract email from PDF content using PyPDF2"""
    pdf_stream = None
    pdf_reader = None
    full_text = ""
    
    try:
        # Create PDF reader from bytes
        pdf_stream = io.BytesIO(pdf_content)
        pdf_reader = PdfReader(pdf_stream)
        
        # Extract text from all pages
        for page in pdf_reader.pages:
            full_text += page.extract_text() + "\n"
        
        # Search for email using regex
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_match = re.search(email_pattern, full_text)
        
        if email_match:
            email = email_match.group()
            
            # Validate email - reject if it starts with "info" or contains "estudio" before "@"
            email_local_part = email.split('@')[0].lower()  # Get part before @ and make lowercase
            
            if email_local_part.startswith('info'):
                print(f"  -> Email validation failed: '{email}' starts with 'info' - rejected")
                return None, "Email rejected: starts with 'info'"
            
            if 'estudio' in email_local_part:
                print(f"  -> Email validation failed: '{email}' contains 'estudio' - rejected")
                return None, "Email rejected: contains 'estudio'"
            
            # Email passed validation - return it
            return email, None
        else:
            return None, "No email found in PDF"
            
    except Exception as e:
        return None, f"Error extracting text from PDF: {e}"
    finally:
        # Always clean up resources
        if pdf_stream:
            pdf_stream.close()
        # Clean up variables to free memory
        del pdf_reader, pdf_stream, full_text

def process_actas():
    """Process all actas from part_data.json"""
    
    # Load JSON data
    try:
        with open('part_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Loaded {len(data['data'])} items from part_data.json")
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return
    
    # Get session with cookies for API requests
    api_session = get_session_with_cookies()
    if not api_session:
        print("Failed to get session with cookies for API. Exiting.")
        return
    
    # Get session with cookies for PDF downloads
    pdf_session = get_session_with_cookies()
    if not pdf_session:
        print("Failed to get session with cookies for PDF downloads. Exiting.")
        return
    
    # Process each acta
    success_count = 0
    error_count = 0
    url_found_count = 0
    email_found_count = 0
    
    for i, item in enumerate(data['data'], 1):
        acta = item.get('Acta')
        if not acta:
            print(f"Item {i}: No acta number found, skipping")
            error_count += 1
            continue
        
        # Build API URL
        api_url = f"https://portaltramites.inpi.gob.ar/Home/GrillaDigitales?limit=100&offset=0&search=&sort=&order=asc&acta={acta}&direccion=1"
        
        try:
            # Make API request
            response = api_session.get(api_url)
            
            if response.status_code == 200:
                print(f"Item {i}: Acta {acta} - SUCCESS (Status: {response.status_code})")
                success_count += 1
                
                # Parse response and find Formulario item
                try:
                    response_data = response.json()
                    formulario_data, error_msg = find_formulario_item(response_data)
                    
                    if formulario_data:
                        # Construct document URL
                        document_url = construct_document_url(
                            formulario_data['id_documento_encriptado'],
                            formulario_data['filename']
                        )
                        print(f"  -> Document URL: {document_url}")
                        url_found_count += 1
                        
                        # Download PDF and extract email
                        pdf_content, pdf_error = download_pdf_with_retry(pdf_session, document_url)
                        
                        if pdf_content:
                            # Extract email from PDF
                            email, email_error = extract_email_from_pdf(pdf_content)
                            
                            if email:
                                print(f"  -> Email found: {email}")
                                email_found_count += 1
                            else:
                                print(f"  -> {email_error}")
                        else:
                            print(f"  -> PDF download failed: {pdf_error}")
                        
                        # Add delay after PDF processing
                        if i < len(data['data']):
                            pdf_delay = random.uniform(0.3, 1.2)
                            time.sleep(pdf_delay)
                            
                    else:
                        print(f"  -> WARNING: {error_msg}")
                        
                except json.JSONDecodeError:
                    print(f"  -> ERROR: Invalid JSON response")
                except Exception as e:
                    print(f"  -> ERROR: {e}")
                    
            else:
                print(f"Item {i}: Acta {acta} - FAILED (Status: {response.status_code})")
                error_count += 1
                
        except Exception as e:
            print(f"Item {i}: Acta {acta} - ERROR: {e}")
            error_count += 1
        
        # Add random delay between requests (except for the last item)
        if i < len(data['data']):
            delay = random.uniform(0.3, 1.2)
            time.sleep(delay)
    
    # Print summary
    print(f"\n=== SUMMARY ===")
    print(f"Total items processed: {len(data['data'])}")
    print(f"Successful requests: {success_count}")
    print(f"Failed requests: {error_count}")
    print(f"Document URLs found: {url_found_count}")
    print(f"Emails extracted: {email_found_count}")

def add_log(message, log_type="info", include_traceback=False):
    if len(message) > MAX_MSG_LEN:
        message = message[:MAX_MSG_LEN] + "…"
    log_record = {
        "message": message,
        "type": log_type,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "traceback": traceback.format_exc() if include_traceback else None
    }
    st.session_state.logs.append(log_record)
    if len(st.session_state.logs) > MAX_LOGS:
        del st.session_state.logs[:len(st.session_state.logs) - MAX_LOGS]

if __name__ == "__main__":
    process_actas() 