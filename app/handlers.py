# app/handlers.py
import re
import json
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import pandas as pd
import io
import httpx

async def solve_from_page_content(
    email: str, 
    secret: str, 
    url: str, 
    body_text: str, 
    html: str, 
    extracted_json: Optional[Dict]
) -> Dict[str, Any]:
    """
    Main dispatcher that analyzes page content and routes to appropriate solver.
    
    Returns:
        Dict containing: email, secret, url, answer, submit_url
    """
    
    # Strategy 1: Check if there's embedded JSON with quiz data
    if extracted_json and isinstance(extracted_json, dict):
        result = await handle_json_quiz(email, secret, url, extracted_json, html)
        if result:
            return result
    
    # Strategy 2: CSV/Excel data analysis tasks
    if any(keyword in body_text.lower() for keyword in ['sum', 'average', 'mean', 'count', 'total']):
        result = await handle_data_analysis(email, secret, url, body_text, html)
        if result:
            return result
    
    # Strategy 3: Simple calculation or number extraction
    if 'calculate' in body_text.lower() or 'compute' in body_text.lower():
        result = await handle_calculation(email, secret, url, body_text, html)
        if result:
            return result
    
    # Fallback: Return debug info
    submit_url = find_submit_url(html)
    return {
        'email': email,
        'secret': secret,
        'url': url,
        'answer': 0,
        'submit_url': submit_url,
        'debug': 'No handler matched',
        'body_snippet': body_text[:300]
    }


async def handle_json_quiz(
    email: str, 
    secret: str, 
    url: str, 
    data: Dict, 
    html: str
) -> Optional[Dict]:
    """
    Handle quizzes where the answer is embedded in JSON.
    """
    # Check if JSON already contains an answer field
    if 'answer' in data:
        answer = data['answer']
    else:
        # Try to compute answer from data
        # Example: if data has numbers, sum them
        answer = extract_answer_from_json(data)
    
    submit_url = data.get('submit') or data.get('submit_url') or find_submit_url(html)
    
    if submit_url:
        return {
            'email': email,
            'secret': secret,
            'url': url,
            'answer': answer,
            'submit_url': submit_url
        }
    
    return None


async def handle_data_analysis(
    email: str, 
    secret: str, 
    url: str, 
    body_text: str, 
    html: str
) -> Optional[Dict]:
    """
    Handle quizzes that require analyzing CSV/Excel files.
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find downloadable files
    file_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(ext in href.lower() for ext in ['.csv', '.xlsx', '.xls', 'download']):
            file_links.append(href)
    
    if not file_links:
        return None
    
    # Parse instruction to understand what to compute
    instruction = body_text.lower()
    
    for file_url in file_links:
        try:
            # Download file
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(file_url)
                resp.raise_for_status()
                file_data = resp.content
            
            # Parse based on file type
            if '.csv' in file_url.lower():
                df = pd.read_csv(io.BytesIO(file_data))
            elif '.xlsx' in file_url.lower() or '.xls' in file_url.lower():
                df = pd.read_excel(io.BytesIO(file_data))
            else:
                continue
            
            # Compute answer based on instruction
            answer = compute_from_dataframe(df, instruction)
            
            if answer is not None:
                submit_url = find_submit_url(html)
                return {
                    'email': email,
                    'secret': secret,
                    'url': url,
                    'answer': answer,
                    'submit_url': submit_url
                }
        
        except Exception as e:
            print(f"Error processing file {file_url}: {e}")
            continue
    
    return None


async def handle_calculation(
    email: str, 
    secret: str, 
    url: str, 
    body_text: str, 
    html: str
) -> Optional[Dict]:
    """
    Handle simple calculation tasks.
    """
    # Extract numbers from text
    numbers = re.findall(r'\b\d+\.?\d*\b', body_text)
    
    if not numbers:
        return None
    
    # Simple heuristic: if instruction mentions sum/add, sum the numbers
    instruction = body_text.lower()
    
    if 'sum' in instruction or 'add' in instruction or 'total' in instruction:
        answer = sum(float(n) for n in numbers)
    elif 'multiply' in instruction or 'product' in instruction:
        answer = 1
        for n in numbers:
            answer *= float(n)
    elif 'average' in instruction or 'mean' in instruction:
        answer = sum(float(n) for n in numbers) / len(numbers)
    else:
        # Default to first number found
        answer = float(numbers[0])
    
    submit_url = find_submit_url(html)
    
    if submit_url:
        return {
            'email': email,
            'secret': secret,
            'url': url,
            'answer': answer,
            'submit_url': submit_url
        }
    
    return None


def compute_from_dataframe(df: pd.DataFrame, instruction: str) -> Optional[float]:
    """
    Compute answer from a DataFrame based on natural language instruction.
    """
    # Extract column name if mentioned
    column = None
    for col in df.columns:
        if col.lower() in instruction:
            column = col
            break
    
    if column is None and len(df.columns) > 0:
        # Default to first numeric column
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                column = col
                break
    
    if column is None:
        return None
    
    # Extract page/row number if mentioned
    page_match = re.search(r'page\s+(\d+)', instruction)
    row_match = re.search(r'row\s+(\d+)', instruction)
    
    if page_match:
        page_num = int(page_match.group(1))
        # Assuming page size of 10 rows (adjust as needed)
        start_idx = (page_num - 1) * 10
        end_idx = start_idx + 10
        df = df.iloc[start_idx:end_idx]
    elif row_match:
        row_num = int(row_match.group(1))
        if row_num <= len(df):
            return float(df.iloc[row_num - 1][column])
    
    # Perform operation
    if 'sum' in instruction or 'total' in instruction:
        return float(df[column].sum())
    elif 'average' in instruction or 'mean' in instruction:
        return float(df[column].mean())
    elif 'count' in instruction:
        return float(df[column].count())
    elif 'max' in instruction or 'maximum' in instruction:
        return float(df[column].max())
    elif 'min' in instruction or 'minimum' in instruction:
        return float(df[column].min())
    
    # Default to sum
    return float(df[column].sum())


def extract_answer_from_json(data: Dict) -> Any:
    """
    Try to extract or compute an answer from JSON data.
    """
    # If there's a 'result' or 'value' field, use it
    for key in ['result', 'value', 'number', 'total']:
        if key in data:
            return data[key]
    
    # If there's a list of numbers, sum them
    for value in data.values():
        if isinstance(value, list) and all(isinstance(x, (int, float)) for x in value):
            return sum(value)
    
    return 0


def find_submit_url(html: str) -> Optional[str]:
    """
    Find the submission URL in the HTML page.
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Look for links with 'submit' in href or text
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text().lower()
        
        if 'submit' in href.lower() or 'submit' in text:
            return href
    
    # Look for form action
    form = soup.find('form')
    if form and form.get('action'):
        return form['action']
    
    # Look for any endpoint-like URL
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/api/' in href or '/task/' in href:
            return href
    
    return None