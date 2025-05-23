import argparse
import cv2
import datetime
from mss import mss
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import time
import threading

SYSTEM_OS        = sys.platform
CAPTURE_FPS      = 60
CAPTURE_INTERVAL = 1.0 / CAPTURE_FPS
EXPECTED_WIDTH = 464
EXPECTED_HEIGHT = 838

if SYSTEM_OS == 'darwin':
	from windowcapture import WindowCapture
elif SYSTEM_OS == 'win32':
	try:
		import pygetwindow as gw
		import win32gui
		import win32con
	except ImportError:
		gw = None  # fallback to per-OS logic
		raise RuntimeError("windows packages not available; please install")
else:
	raise RuntimeError("Unsupported OS. This script only supports macOS (darwin) and Windows (win32).")

class OverlayWindow(QtWidgets.QWidget):
	def __init__(self, stop_event):
		super().__init__(flags=QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
		self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
		self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
		self.regions = []
		self.stop_event = stop_event

		# Cover all monitors
		geom = QtWidgets.QApplication.primaryScreen().geometry()
		for scr in QtWidgets.QApplication.screens():
			geom = geom.united(scr.geometry())
		self.setGeometry(geom)
		self.show()

	def update_regions(self, regions):
		self.regions = regions
		# only repaint if regions changed
		self.update()

	def paintEvent(self, e):
		painter = QtGui.QPainter(self)
		pen = QtGui.QPen(QtGui.QColor(0, 200, 0, 180), 3)
		painter.setPen(pen)
		for r in self.regions:
			painter.drawRect(r['left'], r['top'], r['width'], r['height'])
			
			# Add text inside the rectangle showing left, top, width values
			text = f"({r['left']}, {r['top']}, {r['width']})"
			font = QtGui.QFont("Arial", 10)
			painter.setFont(font)
			# painter.setPen(QtGui.QColor(255, 255, 255))  # White text
			painter.drawText(r['left'] + 5, r['top'] + 20, text)  # Offset for padding

	def closeEvent(self, event):
		print("Closing overlay window...")
		# signal capture thread to stop and let it release the writer
		self.stop_event.set()
		event.accept()

def append_window(rects, w):
	if any(r['left'] == w.left and r['top'] == w.top for r in rects):
		return
	# skip left edge windows
	if w.left <= 1 or w.top <= 1:
		return
	rects.append({
		'left':   w.left,
		'top':    w.top,
		'width':  w.width,
		'height': w.height
	})


def list_window_positions():
	"""
	Enumerate all visible, titled top-level windows.
	Returns a list of dicts with keys:
		- hwnd  : window handle
		- title : window title
		- left, top, width, height
	"""
	windows = []

	def _enum(hwnd, _):
		if win32gui.IsWindowVisible(hwnd):
			title = win32gui.GetWindowText(hwnd).strip()
			if title:
				left, top, right, bottom = win32gui.GetWindowRect(hwnd)
				windows.append({
					'hwnd':   hwnd,
					'title':  title,
					'left':   left,
					'top':    top,
					'width':  right - left,
					'height': bottom - top
				})

	win32gui.EnumWindows(_enum, None)
	return windows

def resize_window(title, x, y, width, height):
	# hwnd = win32gui.FindWindow(None, title)
	windows = list_window_positions()
	for w in windows:
		if w['title'] == title and w['left'] == x and w['top'] == y:
			selected_hwnd = w['hwnd']
			title = w['title']
			break

	print(f"Window: {title} ({x}, {y}, {width}, {height})")
	if not selected_hwnd:
		raise ValueError(f"Window with title '{title}' not found")
	win32gui.SetWindowPos(
		selected_hwnd, None,
		x, y, width, height,
		win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
	)

def find_windows(title):
	"""Return list of dicts with left, top, width, height for each live window."""
	rects = []
	if SYSTEM_OS == 'win32':
		for w in gw.getWindowsWithTitle(title):
			if not w.visible or w.isMinimized:
				continue
			append_window(rects, w)
		for rect in rects:
			if rect['width'] != EXPECTED_WIDTH or rect['height'] != EXPECTED_HEIGHT:
				print(f"Resizing window {title} from {rect['width']}x{rect['height']} to {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")
				resize_window(title, rect['left'], rect['top'], EXPECTED_WIDTH, EXPECTED_HEIGHT)

	elif SYSTEM_OS == 'darwin':
		wc = WindowCapture(title)
		if wc.window is not None:
			w = wc.window
			if not w.isMinimized:
				append_window(rects, w)
	#order the rects to prevent flickering between windows
	rects.sort(key=lambda r: (r['top'], r['left']))
	return rects

def capture_loop(overlay: OverlayWindow, stop_event: threading.Event, target_title: str, output_prefix: str):
	sct = mss()
	video_writers = [None] * 10  # preallocate for 10 windows
	while not stop_event.is_set():
		rects = find_windows(target_title)
		overlay.update_regions(rects)
		if rects:
			for i,r in enumerate(rects):
				w, h = r['width'], r['height']
				rect = {'left': r['left'], 'top': r['top'], 'width': w, 'height': h}
				# lazily initialize VideoWriter once we know size
				if video_writers[i] is None:
					# print("rect:", union_rect)
					fourcc   = cv2.VideoWriter_fourcc(*'mp4v')
					timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
					filename  = f"{output_prefix}capture_{i}_{timestamp}.mp4"
					#handle macOS retina display scaling
					if SYSTEM_OS == 'darwin':
						w = int(w * 2)
						h = int(h * 2)
					video_writers[i] = cv2.VideoWriter(
						filename, fourcc, CAPTURE_FPS, (w, h)
					)
					print(f"Recording to {output_prefix}{filename} @ {CAPTURE_FPS} FPS...")
				# grab the region
				frame = np.array(sct.grab(rect))
				# MSS gives BGRA; drop alpha and convert to BGR
				bgr   = cv2.cvtColor(frame[..., :3], cv2.COLOR_RGB2BGR)
				video_writers[i].write(bgr)
		time.sleep(CAPTURE_INTERVAL)

	print("Stopping capture...")
	for video_writer in video_writers:
		if video_writer is not None:
			video_writer.release()
			print("Recording finished and file closed.")

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Screen capture application.")
	parser.add_argument(
		"--title", type=str, default='Calculator',
		help="Window title to capture (default: Calculator)"
	)
	parser.add_argument(
		"--output", type=str, default='',
		help="Output file destination prefix (default: current directory)"
	)
	args = parser.parse_args()

	app = QtWidgets.QApplication(sys.argv)
	stop_event = threading.Event()
	overlay = OverlayWindow(stop_event)
	capture_thread = threading.Thread(target=capture_loop, args=(overlay, stop_event, args.title, args.output))
	print("Starting capture thread...")
	capture_thread.start()
	sys.exit(app.exec_())