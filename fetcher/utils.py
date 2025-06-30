import bs4
import os
import re
import mistune
import logging
import subprocess
import argparse
import requests
from tqdm import tqdm

from requests.exceptions import ConnectionError, HTTPError
from urllib.parse import urlparse, parse_qs

def list_txt_files(directory):
    txt_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.txt'):
                txt_files.append(os.path.join(root, file))
    return txt_files

def extract_hrefs_from_markdown(markdown_file):
    with open(markdown_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    as_html = mistune.html(content)
    
    soup = bs4.BeautifulSoup(as_html, 'html.parser')
    hrefs = [a.get('href') for a in soup.find_all('a', href=True)]
    
    return hrefs
    
def hocr_to_txt(hocr_file, txt_file):
    result = subprocess.run(['hocr-lines', hocr_file], capture_output=True, text=True)
    
    if result.returncode == 0:
        with open(txt_file, 'w', encoding='utf-8') as file:
            file.write(result.stdout)
        logging.info(f"Converted {hocr_file} to {txt_file}")
    else:
        logging.error(f"Error converting {hocr_file}: {result.stderr}")

def convert_all_hocr_files(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for filename in tqdm(os.listdir(input_dir), desc="Converting hocr"):
        if filename.endswith('.hocr'):
            hocr_file = os.path.join(input_dir, filename)
            txt_filename = filename.replace('.hocr', '.txt')
            txt_file = os.path.join(output_dir, txt_filename)
            
            hocr_to_txt(hocr_file, txt_file)

def list_directories(path):
    directories = [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]
    return directories

def get_query_value(url, key):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    value = query_params.get(key, [None])[0]
    return value

def datum_to_iso_8601(datum):
    return "-".join([datum[0:4], datum[4:6], datum[6:]])

def download_remote_file(url, path, session):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    try:
        response = session.get(url, stream=True)
        response.raise_for_status() 
        
        with open(path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        logging.info(f"File downloaded successfully to {path}")
    
    except ConnectionError as e:
        logging.error(f"Connection error occurred: {e}")
    except HTTPError as e:
        logging.error(f"HTTP error occurred: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def delete_file(file_path):
    try:
        os.remove(file_path)
        logging.error(f"File '{file_path}' deleted successfully.")
    except FileNotFoundError:
        logging.error(f"File '{file_path}' not found.")
    except PermissionError:
        logging.error(f"Permission denied to delete '{file_path}'.")
    except Exception as e:
        logging.error(f"Error deleting file '{file_path}': {e}")

def remove_newlines(text):
    return text.replace("\n", "")

def split_anno_x_file(file_path, output_dir):
    content = read_multi_encoding(file_path)
    
    header_pattern = re.compile(r'\[\s*.*?Seite\s*\d+\s*\]')

    pages = header_pattern.split(content)
    
    if pages[0].strip() == '':
        pages.pop(0)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, page in enumerate(pages, start=1):
        with open(os.path.join(output_dir, f'{i}.txt'), 'w', encoding='utf-8') as output_file:
            output_file.write(page.strip())

def read_multi_encoding(file_path) -> str:
    encoding = 'utf-8'
    content = None

    while content is None:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
        except UnicodeDecodeError as e:
            logging.error(e)
            logging.error(f"File {file_path} does not appear to be UTF-8 encoded. Trying 'latin-1'...")
            encoding = 'latin-1' # Try 'latin-1' encoding instead!
            continue
        except Exception as e:
            logging.error(f"Unable to decode file {file_path}.")
            raise e
        finally:
            if encoding == 'latin-1' and content:
                # Re-encode as utf-8
                content = content.encode("utf-8", errors="replace").decode('utf-8')
                logging.info(f"Re-encoded {file_path} as utf-8. Content may not be accurate.")

    return content

def get_all_hrefs(url, session):
    response = session.get(url)
    
    if response.status_code == 200:
        soup = bs4.BeautifulSoup(response.content, 'html.parser')
        hrefs = [a.get('href') for a in soup.find_all('a', href=True)]
        
        return hrefs
    else:
        return []
    
def main():
    parser = argparse.ArgumentParser(description="Utility script with multiple subcommands.")
    subparsers = parser.add_subparsers(dest="command")

    parser_extract_hrefs = subparsers.add_parser("extract_hrefs", help="Extract hrefs from a markdown file.")
    parser_extract_hrefs.add_argument("markdown_file", type=str, help="Path to the markdown file.")

    parser_hocr_to_txt = subparsers.add_parser("hocr_to_txt", help="Convert HOCR file to TXT file.")
    parser_hocr_to_txt.add_argument("hocr_file", type=str, help="Path to the HOCR file.")
    parser_hocr_to_txt.add_argument("txt_file", type=str, help="Path to the output TXT file.")

    parser_convert_all_hocr = subparsers.add_parser("convert_all_hocr", help="Convert all HOCR files in a directory to TXT files.")
    parser_convert_all_hocr.add_argument("input_dir", type=str, help="Directory containing HOCR files.")
    parser_convert_all_hocr.add_argument("output_dir", type=str, help="Directory to save TXT files.")

    parser_list_directories = subparsers.add_parser("list_directories", help="List all directories in a given path.")
    parser_list_directories.add_argument("path", type=str, help="Path to list directories from.")

    parser_get_query_value = subparsers.add_parser("get_query_value", help="Get query value from a URL.")
    parser_get_query_value.add_argument("url", type=str, help="URL to parse.")
    parser_get_query_value.add_argument("key", type=str, help="Query key to get value for.")

    parser_download_remote_file = subparsers.add_parser("download_remote_file", help="Download a remote file.")
    parser_download_remote_file.add_argument("url", type=str, help="URL of the remote file.")
    parser_download_remote_file.add_argument("path", type=str, help="Path to save the downloaded file.")

    parser_split_anno_x_file = subparsers.add_parser("split_anno_x_file", help="Split a file based on 'Seite' headers.")
    parser_split_anno_x_file.add_argument("file_path", type=str, help="Path to the file to split.")
    parser_split_anno_x_file.add_argument("output_dir", type=str, help="Directory to save TXT files.")

    parser_get_all_hrefs = subparsers.add_parser("get_all_hrefs", help="Get all hrefs from a URL.")
    parser_get_all_hrefs.add_argument("url", type=str, help="URL to get hrefs from.")

    args = parser.parse_args()

    if args.command == "extract_hrefs":
        hrefs = extract_hrefs_from_markdown(args.markdown_file)
        logging.info("\n".join(hrefs))
    elif args.command == "hocr_to_txt":
        hocr_to_txt(args.hocr_file, args.txt_file)
    elif args.command == "convert_all_hocr":
        convert_all_hocr_files(args.input_dir, args.output_dir)
    elif args.command == "list_directories":
        directories = list_directories(args.path)
        logging.info(directories)
    elif args.command == "get_query_value":
        value = get_query_value(args.url, args.key)
        logging.info(value)
    elif args.command == "download_remote_file":
        session = requests.Session()
        download_remote_file(args.url, args.path, session)
    elif args.command == "split_anno_x_file":
        session = requests.Session()
        split_anno_x_file(args.file_path, args.output_dir)
    elif args.command == "get_all_hrefs":
        session = requests.Session()
        hrefs = get_all_hrefs(args.url, session)
        logging.info(hrefs)

if __name__ == "__main__":
    main()
