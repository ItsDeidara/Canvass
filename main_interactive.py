import sys
import os
import configparser
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QFileDialog, QLabel, QLineEdit, QFormLayout, QMessageBox, QDialog, QComboBox, QTextEdit
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QTextCursor
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
import datetime
from main import translate_gcode, upload_file, connect_to_printer  # Import functions from main.py
import asyncio

class GCodeViewer(QWidget):
    offset_changed = Signal(QPointF)  # New signal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gcode_paths = []
        self.gcode_offset = QPointF(0, 0)
        self.dragging = False
        self.last_pos = QPointF(0, 0)
        self.scale_factor = 1.0
        self.min_x = float('inf')
        self.min_y = float('inf')
        self.max_x = float('-inf')
        self.max_y = float('-inf')
        self.bed_size = (220, 220)

    def load_gcode(self, filename):
        self.gcode_paths = []
        self.min_x = float('inf')
        self.min_y = float('inf')
        self.max_x = float('-inf')
        self.max_y = float('-inf')
        
        with open(filename, 'r') as file:
            for line in file:
                if line.startswith(('G0', 'G1')):
                    parts = line.split()
                    new_pos = QPointF()
                    for part in parts:
                        if part.startswith('X'):
                            new_pos.setX(float(part[1:]))
                        elif part.startswith('Y'):
                            new_pos.setY(float(part[1:]))
                    
                    if len(self.gcode_paths) == 0:
                        self.gcode_paths.append((new_pos, new_pos))
                    else:
                        self.gcode_paths.append((self.gcode_paths[-1][1], new_pos))
                    
                    # Update min and max coordinates
                    self.min_x = min(self.min_x, new_pos.x())
                    self.min_y = min(self.min_y, new_pos.y())
                    self.max_x = max(self.max_x, new_pos.x())
                    self.max_y = max(self.max_y, new_pos.y())
        
        print(f"Loaded {len(self.gcode_paths)} paths")
        print(f"Min X: {self.min_x}, Max X: {self.max_x}")
        print(f"Min Y: {self.min_y}, Max Y: {self.max_y}")
        
        self.fit_view()
        self.update()

    def fit_view(self):
        if self.gcode_paths:
            width = self.max_x - self.min_x
            height = self.max_y - self.min_y
            
            # Calculate scale factor to fit the view
            self.scale_factor = min(self.width() / self.bed_size[0], self.height() / self.bed_size[1]) * 0.9
            
            # Don't center the GCode, keep its original position
            self.gcode_offset = QPointF(0, 0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate the bed rectangle in widget coordinates
        bed_rect = QRectF(
            self.width() / 2 - self.bed_size[0] * self.scale_factor / 2,
            self.height() / 2 - self.bed_size[1] * self.scale_factor / 2,
            self.bed_size[0] * self.scale_factor,
            self.bed_size[1] * self.scale_factor
        )
        
        # Draw the grid
        self.draw_grid(painter, bed_rect)
        
        # Draw the GCode
        painter.save()
        painter.setClipRect(bed_rect)
        painter.translate(bed_rect.topLeft())
        painter.scale(self.scale_factor, -self.scale_factor)  # Invert Y-axis
        painter.translate(self.gcode_offset)
        painter.translate(0, -self.bed_size[1])  # Translate to bottom-left corner

        pen = QPen(QColor(0, 0, 255))
        pen.setWidth(1 / self.scale_factor)
        painter.setPen(pen)

        for start, end in self.gcode_paths:
            painter.drawLine(start, end)
        
        painter.restore()

    def draw_grid(self, painter, bed_rect):
        grid_color = QColor(200, 200, 200)
        text_color = QColor(100, 100, 100)
        painter.setPen(QPen(grid_color))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        # Draw vertical lines
        for x in range(0, int(self.bed_size[0]) + 1, 10):
            scaled_x = x * self.scale_factor + bed_rect.left()
            painter.drawLine(QPointF(scaled_x, bed_rect.top()), QPointF(scaled_x, bed_rect.bottom()))
            if x % 50 == 0:
                painter.setPen(text_color)
                painter.drawText(QPointF(scaled_x + 2, bed_rect.bottom() - 10), str(x))
                painter.setPen(grid_color)

        # Draw horizontal lines
        for y in range(0, int(self.bed_size[1]) + 1, 10):
            scaled_y = bed_rect.bottom() - y * self.scale_factor  # Invert Y-axis
            painter.drawLine(QPointF(bed_rect.left(), scaled_y), QPointF(bed_rect.right(), scaled_y))
            if y % 50 == 0:
                painter.setPen(text_color)
                painter.drawText(QPointF(bed_rect.left() + 2, scaled_y + 12), str(y))
                painter.setPen(grid_color)

        # Label front and back of the bed
        painter.setPen(text_color)
        painter.drawText(QPointF(bed_rect.center().x() - 15, bed_rect.bottom() + 20), "FRONT")
        painter.drawText(QPointF(bed_rect.center().x() - 15, bed_rect.top() - 10), "BACK")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_pos = event.position()

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.position() - self.last_pos
            # Invert the Y-axis delta
            self.gcode_offset += QPointF(delta.x(), -delta.y()) / self.scale_factor
            self.last_pos = event.position()
            self.update()
            self.offset_changed.emit(self.get_offset())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False

    def wheelEvent(self, event):
        zoom_factor = 1.2
        old_pos = self.mapToScene(event.position().toPoint())
        
        if event.angleDelta().y() > 0:
            self.scale_factor *= zoom_factor
        else:
            self.scale_factor /= zoom_factor
        
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.gcode_offset += QPointF(delta.x(), -delta.y())  # Invert Y-axis
        self.update()
        self.offset_changed.emit(self.get_offset())

    def mapToScene(self, pos):
        bed_rect = QRectF(
            self.width() / 2 - self.bed_size[0] * self.scale_factor / 2,
            self.height() / 2 - self.bed_size[1] * self.scale_factor / 2,
            self.bed_size[0] * self.scale_factor,
            self.bed_size[1] * self.scale_factor
        )
        return QPointF(
            (pos.x() - bed_rect.left()) / self.scale_factor,
            (bed_rect.bottom() - pos.y()) / self.scale_factor  # Invert Y-axis
        )

    def get_offset(self):
        return QPointF(
            -self.gcode_offset.x(),
            -self.gcode_offset.y()
        )

class ConfigDialog(QDialog):
    def __init__(self, config_file_path):
        super().__init__()
        self.setWindowTitle("Configuration")
        self.config_file_path = config_file_path
        self.config = configparser.ConfigParser()
        self.config.read(config_file_path)
        
        layout = QFormLayout()
        
        self.url_input = QLineEdit(self.config.get('Moonraker', 'url'))
        layout.addRow("Moonraker URL:", self.url_input)
        
        self.auto_upload_input = QComboBox()
        self.auto_upload_input.addItems(['true', 'false'])
        self.auto_upload_input.setCurrentText(self.config.get('Moonraker', 'auto_upload'))
        layout.addRow("Auto Upload:", self.auto_upload_input)
        
        self.auto_start_print_input = QComboBox()
        self.auto_start_print_input.addItems(['true', 'false'])
        self.auto_start_print_input.setCurrentText(self.config.get('Moonraker', 'auto_start_print'))
        layout.addRow("Auto Start Print:", self.auto_start_print_input)
        
        self.include_timestamp_input = QComboBox()
        self.include_timestamp_input.addItems(['true', 'false'])
        self.include_timestamp_input.setCurrentText(self.config.get('Script', 'include_timestamp'))
        layout.addRow("Include Timestamp:", self.include_timestamp_input)
        
        self.autowatch_input = QComboBox()
        self.autowatch_input.addItems(['true', 'false'])
        self.autowatch_input.setCurrentText(self.config.get('Script', 'autowatch'))
        layout.addRow("Autowatch:", self.autowatch_input)
        
        self.watch_interval_input = QLineEdit(self.config.get('Script', 'watch_interval'))
        layout.addRow("Watch Interval:", self.watch_interval_input)
        
        save_button = QPushButton("Save Config")
        save_button.clicked.connect(self.save_config)
        layout.addRow(save_button)
        
        self.setLayout(layout)

    def save_config(self):
        self.config.set('Moonraker', 'url', self.url_input.text())
        self.config.set('Moonraker', 'auto_upload', self.auto_upload_input.currentText())
        self.config.set('Moonraker', 'auto_start_print', self.auto_start_print_input.currentText())
        self.config.set('Script', 'include_timestamp', self.include_timestamp_input.currentText())
        self.config.set('Script', 'autowatch', self.autowatch_input.currentText())
        self.config.set('Script', 'watch_interval', self.watch_interval_input.text())
        
        with open(self.config_file_path, 'w') as configfile:
            self.config.write(configfile)
        
        QMessageBox.information(self, "Config Saved", "Configuration has been updated.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Canvass")
        self.setGeometry(100, 100, 800, 800)  # Increased height to accommodate status area

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        self.gcode_viewer = GCodeViewer()
        self.gcode_viewer.offset_changed.connect(self.update_offset_label)
        layout.addWidget(self.gcode_viewer)

        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        load_button = QPushButton("Load GCode")
        load_button.clicked.connect(self.load_gcode)
        button_layout.addWidget(load_button)

        fix_button = QPushButton("Fix GCode")
        fix_button.clicked.connect(self.fix_gcode)
        button_layout.addWidget(fix_button)

        upload_button = QPushButton("Upload to Mainsail")
        upload_button.clicked.connect(self.upload_to_mainsail)
        button_layout.addWidget(upload_button)

        config_button = QPushButton("Config")
        config_button.clicked.connect(self.show_config_dialog)
        button_layout.addWidget(config_button)

        self.offset_label = QLabel("Offset: X=0.00, Y=0.00")
        button_layout.addWidget(self.offset_label)

        # Add status area
        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setMinimumHeight(100)
        self.status_area.setMaximumHeight(150)  # Limit the height of the status area
        layout.addWidget(self.status_area)

        self.current_file = None
        self.config_file_path = 'config.ini'
        self.config = configparser.ConfigParser()
        self.config.read(self.config_file_path)

    def update_status(self, message):
        self.status_area.append(message)
        self.status_area.moveCursor(QTextCursor.End)
        self.status_area.ensureCursorVisible()

    def load_gcode(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open GCode File", "fixme", "GCode Files (*.gcode)")
        if filename:
            self.update_status(f"Loading file: {filename}")
            self.current_file = filename
            self.gcode_viewer.load_gcode(filename)
            self.update_offset_label(self.gcode_viewer.get_offset())
            self.update_status("File loaded successfully.")

    def fix_gcode(self):
        if not self.current_file:
            self.update_status("No file loaded. Please load a GCode file first.")
            return

        offset = self.gcode_viewer.get_offset()
        x_offset, y_offset = offset.x(), offset.y()
        self.offset_label.setText(f"Offset: X={x_offset:.2f}, Y={y_offset:.2f}")
        
        self.update_status(f"Fixing GCode with offset: X={x_offset:.2f}, Y={y_offset:.2f}")
        
        output_directory = 'fixed'
        os.makedirs(output_directory, exist_ok=True)
        
        base_name = os.path.basename(self.current_file)
        name, ext = os.path.splitext(base_name)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{name}-FIXED_X{x_offset:.1f}_Y{y_offset:.1f}_{timestamp}{ext}"
        output_file_path = os.path.join(output_directory, new_filename)

        translate_gcode(self.current_file, output_file_path, -x_offset, -y_offset)
        
        self.update_status(f"Fixed GCode saved as: {output_file_path}")
        self.current_file = output_file_path

    def upload_to_mainsail(self):
        if not self.current_file:
            self.update_status("No file loaded. Please load or fix a GCode file first.")
            return

        self.update_status("Processing... please wait...")
        QApplication.processEvents()  # Force the GUI to update

        url = self.config.get('Moonraker', 'url')
        auto_start_print = self.config.getboolean('Moonraker', 'auto_start_print')

        async def upload():
            self.update_status(f"Connecting to Mainsail at {url}...")
            client = await connect_to_printer(url)
            if client:
                self.update_status("Connected to Mainsail. Uploading file...")
                await upload_file(client, self.current_file)
                self.update_status("File uploaded successfully.")
                if auto_start_print:
                    self.update_status("Auto-start print is enabled, but not implemented in this version.")
                await client.disconnect()
                self.update_status("Disconnected from Mainsail.")
            else:
                self.update_status("Failed to connect to Mainsail.")

        asyncio.run(upload())

    def show_config_dialog(self):
        config_dialog = ConfigDialog(self.config_file_path)
        config_dialog.setWindowModality(Qt.ApplicationModal)
        if config_dialog.exec():
            self.update_status("Configuration updated.")
        else:
            self.update_status("Configuration update cancelled.")

    def update_offset_label(self, offset):
        self.offset_label.setText(f"Offset: X={offset.x():.2f}, Y={offset.y():.2f}")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()