import configparser
import os
import asyncio
import logging
from moonraker_api import MoonrakerClient, MoonrakerListener
from aiohttp.client_exceptions import ClientConnectorError
import urllib.parse
import datetime
import aiohttp
import re
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_default_config(config_file_path):
    config = configparser.ConfigParser()
    config['Offsets'] = {
        'x_offset': '80',
        'y_offset': '80'
    }
    config['Moonraker'] = {
        'url': 'http://localhost:7125',
        'auto_upload': 'true',
        'auto_start_print': 'false'
    }
    config['Script'] = {
        'include_timestamp': 'false',
        'autowatch': 'false',
        'watch_interval': '60'
    }
    with open(config_file_path, 'w') as configfile:
        config.write(configfile)
    print(f"Created default config file at {config_file_path}")

def translate_gcode(input_file_path, output_file_path, x_offset, y_offset):
    print(f"Translating GCode with offsets: X={x_offset}, Y={y_offset}")
    with open(input_file_path, 'r') as file:
        lines = file.readlines()

    with open(output_file_path, 'w') as file:
        # Add a comment with the offset information at the beginning of the file
        file.write(f"; Translated with offsets: X={x_offset}mm, Y={y_offset}mm\n")
        
        for line in lines:
            if line.startswith(('G0', 'G1')):  # Check for movement commands
                parts = line.split()
                new_parts = []
                for part in parts:
                    if part.startswith('X'):
                        x_value = float(part[1:])
                        new_x_value = x_value + x_offset  # Add the offset instead of subtracting
                        new_parts.append(f'X{new_x_value:.3f}')
                    elif part.startswith('Y'):
                        y_value = float(part[1:])
                        new_y_value = y_value + y_offset  # Add the offset instead of subtracting
                        new_parts.append(f'Y{new_y_value:.3f}')
                    else:
                        new_parts.append(part)
                new_line = ' '.join(new_parts)
                file.write(new_line + '\n')
            else:
                file.write(line)

class MyMoonrakerListener(MoonrakerListener):
    async def state_changed(self, state: str) -> None:
        logging.info(f"Moonraker connection state changed to: {state}")

async def connect_to_printer(url):
    try:
        parsed_url = urllib.parse.urlparse(url)
        host = parsed_url.hostname
        port = parsed_url.port or 7125  # Default to 7125 if no port is specified
        base_url = f"{parsed_url.scheme}://{host}:{port}"
        logging.info(f"Attempting to connect to Moonraker at {base_url}")
        client = MoonrakerClient(MyMoonrakerListener(), host, port)
        await client.connect()
        client._base_url = base_url  # Store the base URL in the client object
        return client
    except ClientConnectorError as e:
        logging.error(f"Failed to connect to Moonraker at {url}. Error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error while connecting to Moonraker: {e}")
        return None

async def upload_file(client, file_path):
    original_file_name = os.path.basename(file_path)
    
    # Create a URL-friendly filename
    url_friendly_name = re.sub(r'[^\w\-_\.]', '_', original_file_name)
    url_friendly_name = url_friendly_name.replace(' ', '_')
    
    url = f"{client._base_url}/server/files/upload"
    
    with open(file_path, 'rb') as file:
        data = aiohttp.FormData()
        data.add_field('file', file, filename=url_friendly_name)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 201:
                    logging.info(f"Uploaded {original_file_name} to printer as {url_friendly_name}")
                else:
                    logging.error(f"Failed to upload {original_file_name}. Status: {response.status}")
                    response_text = await response.text()
                    logging.error(f"Response: {response_text}")

async def start_print(client, file_name):
    await client.call_method("printer.print.start", filename=file_name)
    print(f"Started printing {file_name}")

def validate_moonraker_url(url):
    parsed_url = urllib.parse.urlparse(url)
    if not all([parsed_url.scheme, parsed_url.hostname, parsed_url.port]):
        raise ValueError(f"Invalid Moonraker URL: {url}. It should be in the format 'http://hostname:port'")

async def process_files(input_directory, output_directory, x_offset, y_offset, include_timestamp, client, auto_upload, auto_start_print):
    for filename in os.listdir(input_directory):
        if filename.endswith('.gcode'):
            input_file_path = os.path.join(input_directory, filename)
            base_name, ext = os.path.splitext(filename)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") if include_timestamp else ""
            timestamp_part = f"_{timestamp}" if timestamp else ""
            
            new_filename = f"{base_name.replace(' ', '_').replace('(', '').replace(')', '')}-FIXED_X{x_offset:.1f}_Y{y_offset:.1f}{timestamp_part}{ext}"
            output_file_path = os.path.join(output_directory, new_filename)
            
            translate_gcode(input_file_path, output_file_path, x_offset, y_offset)
            logging.info(f"Processed {filename} -> {new_filename}")
            
            if auto_upload and client:
                try:
                    await upload_file(client, output_file_path)
                    
                    if auto_start_print:
                        logging.info(f"Auto-start print is enabled. Starting print of {new_filename}")
                        await start_print(client, new_filename)
                    else:
                        logging.info("Auto-start print is disabled. Skipping print start.")
                except Exception as e:
                    logging.error(f"Failed to upload or start print: {e}")
            else:
                logging.info(f"Auto-upload is disabled. Skipping upload of {new_filename}")
            
            # Move the processed file to a 'processed' subdirectory
            processed_dir = os.path.join(input_directory, 'processed')
            os.makedirs(processed_dir, exist_ok=True)
            os.rename(input_file_path, os.path.join(processed_dir, filename))

async def main_async():
    config_file_path = 'config.ini'
    
    if not os.path.exists(config_file_path):
        create_default_config(config_file_path)
    
    config = configparser.ConfigParser()
    config.read(config_file_path)
    
    x_offset = config.getfloat('Offsets', 'x_offset')
    y_offset = config.getfloat('Offsets', 'y_offset')
    
    moonraker_url = config.get('Moonraker', 'url')
    auto_upload = config.getboolean('Moonraker', 'auto_upload')
    auto_start_print = config.getboolean('Moonraker', 'auto_start_print')
    
    include_timestamp = config.getboolean('Script', 'include_timestamp')
    autowatch = config.getboolean('Script', 'autowatch')
    watch_interval = config.getint('Script', 'watch_interval')
    
    logging.info(f"Auto-upload is set to: {auto_upload}")
    logging.info(f"Auto-start print is set to: {auto_start_print}")
    logging.info(f"Include timestamp is set to: {include_timestamp}")
    logging.info(f"Autowatch is set to: {autowatch}")

    input_directory = 'fixme'
    output_directory = 'fixed'
    
    os.makedirs(output_directory, exist_ok=True)
    
    client = None
    if auto_upload or auto_start_print:
        client = await connect_to_printer(moonraker_url)
        if client is None:
            logging.warning("Failed to connect to Moonraker. Continuing without upload/print functionality.")
            auto_upload = False
            auto_start_print = False
        else:
            try:
                printer_info = await client.get_host_info()
                logging.info(f"Connected to printer: {printer_info['hostname']}")
            except Exception as e:
                logging.error(f"Failed to get host info: {e}")
                await client.disconnect()
                client = None
                auto_upload = False
                auto_start_print = False
    
    while True:
        await process_files(input_directory, output_directory, x_offset, y_offset, include_timestamp, client, auto_upload, auto_start_print)
        
        if not autowatch:
            break
        
        logging.info(f"Waiting {watch_interval} seconds before checking for new files...")
        await asyncio.sleep(watch_interval)

    if client:
        await client.disconnect()

def main():
    try:
        logging.info("Starting the script...")
        asyncio.run(main_async())
        logging.info("Script completed successfully.")
    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()