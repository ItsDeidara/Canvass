### Project Description: Canvass - GCode Fixer and Uploader

**Canvass** is a tool designed to fix the lingering issues with MosaicMFG's seemingly abandoned product. [Canvas3D](https://canvas3d.io/projects)

Despite what you see in the Canvas slicer, it does not generate G-code correctly. While the model may appear centered on the build plate in Canvas, the actual G-code output is offset by about 100mm in both the X and Y directions. This tool resolves that problem by fixing the G-code, and also offers the option to upload the corrected G-code to your printer via Mainsail. Additionally, you can choose to automatically start the print if desired, assuming you have a Moonraker instance already connected to a Palette 2 (or 2S).

## Usage

### Command-Line Interface: `main.py`

1. **Setup**: Place your GCode files in the `fixme` directory.
2. **Run the Script**: Execute the script using Python:
   ```bash
   python main.py
   ```
3. **Output**: Processed GCode files will be saved in the `fixed` directory with filenames indicating the applied offsets, e.g., `filename-FIXED-X80-Y80.gcode`.

### Graphical User Interface: `main_interactive.py`

1. **Launch the GUI**: Start the application with:
   ```bash
   python main_interactive.py
   ```
2. **Load GCode**: Use the "Load GCode" button to select a file from the `fixme` directory.
3. **Fix GCode**: Adjust the offsets using the viewer and click "Fix GCode" to apply the changes. The fixed file will be saved in the `fixed` directory.
4. **Upload to Mainsail**: If configured, use the "Upload to Mainsail" button to upload the fixed file to your 3D printer.
5. **Configuration**: Access the "Config" button to modify settings such as the Moonraker URL and auto-upload options.

## Features

- **Offset Adjustment**: Easily translate GCode coordinates by specified offsets.
- **Batch Processing**: Automatically process all GCode files in the `fixme` directory.
- **Moonraker Integration**: Upload and optionally start prints directly from the application.
- **Interactive GUI**: Visualize and adjust GCode paths with a user-friendly interface.

## Troubleshooting

- Ensure all dependencies are installed and up-to-date.
- Verify the `config.ini` file is correctly formatted and accessible.
- Check network connectivity if experiencing issues with Moonraker integration.

For further assistance, please refer to the documentation or contact support.