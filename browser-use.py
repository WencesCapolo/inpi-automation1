import requests
import json

part_data = json.load(open('part_data.json', 'r'))


url = "https://api.browser-use.com/api/v1/run-task"

payload = {
    "task": "1. Go to https://portaltramites.inpi.gob.ar/marcasconsultas/busqueda/?Cod_Funcion=NQA0ADEA. 2. Search for NUMERO DE ACTA 4367076, click on buscar and wait for the page to load. 3. Click on the plus blue little button of the last column, wait for the new page to load. 5. Click on GRILLA DIGITAL (do not scroll down it is at viewport), wait for the new page to load. 7. Copy the link of descargar (blue text) that has the value 'Formulario' on the Indice column, and return the link as a string.",
    "secrets": {},
    "allowed_domains": ["portaltramites.inpi.gob.ar"],
    "save_browser_data": True,
    "structured_output_json": "{\"type\": \"object\", \"properties\": {\"url\": {\"type\": \"string\"}}, \"required\": [\"url\"]}",
    "llm_model": "claude-3-7-sonnet-20250219",
    "use_adblock": True,
    "use_proxy": True,
    "proxy_country_code": "us",
    "highlight_elements": True,
    "included_file_names": ["<string>"]
}   
headers = {
    "Authorization": "Bearer bu_ahp_VLVZ40snRa1plhrZg0GzO2zUEvpnwqzXQ_-YrUs",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)