import sys
import time
import threading
import datetime

from mss import mss
import numpy as np
import cv2

SYSTEM_OS = sys.platform

if SYSTEM_OS == 'darwin':
	from windowcapture import WindowCapture
elif SYSTEM_OS == 'win32':
	try:
		import pygetwindow as gw
	except ImportError:
		gw = None  # fallback to per-OS logic
		raise RuntimeError("pygetwindow not available; please install it.")
else:
	raise RuntimeError("Unsupported OS. This script only supports macOS (darwin) and Windows (win32).")

from PyQt5 import QtWidgets, QtCore, QtGui
import argparse

CAPTURE_FPS      = 15               # desired capture frame-rate
CAPTURE_INTERVAL = 1.0 / CAPTURE_FPS

class OverlayWindow(QtWidgets.QWidget):
	def __init__(self, stop_event):
		super().__init__(flags=QtCore.Qt.FramelessWindowHint
						  | QtCore.Qt.WindowStaysOnTopHint)
						#   | QtCore.Qt.TransparentForMouseEvents)
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

def find_windows(title):
	"""Return list of dicts with left, top, width, height for each live window."""
	rects = []
	if SYSTEM_OS == 'win32':
		for w in gw.getWindowsWithTitle(title):
			if not w.visible or w.isMinimized:
				continue
			if any(r['left'] == w.left and r['top'] == w.top for r in rects):
				continue
			# skip the first window if it is at (0,0)
			if any(r['left'] <= 0 or r['top'] <= 0 for r in rects):
				continue
			rects.append({
				'left':   w.left,
				'top':    w.top,
				'width':  w.width,
				'height': w.height
			})
	elif SYSTEM_OS == 'darwin':
		wc = WindowCapture(title)
		if wc.window is not None:
			rects.append({
				'left':   wc.window_x,
				'top':    wc.window_y,
				'width':  wc.window_width,
				'height': wc.window_height
			})
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