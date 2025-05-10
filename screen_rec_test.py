from mss import mss
import numpy as np
import cv2
import time

CAPTURE_FPS = 20.0
CAPTURE_INTERVAL = 1.0 / CAPTURE_FPS

def capture_loop():
	sct = mss()
	video_writer = None
	union_rect = None
	# while not stop_event.is_set():
	i = 0
	left, top     = 50, 50
	# right, bot    = 250, 250
	# w, h          = int(right - left), int(bot - top)
	w, h = 640, 480
	union_rect = {'left': left, 'top': top, 'width': w/2, 'height': h/2}
	while i < 100:

		# lazily initialize VideoWriter once we know size
		if video_writer is None:
			fourcc   = cv2.VideoWriter_fourcc(*'mp4v')
			# fourcc = cv2.VideoWriter_fourcc(*'XVID')
			# timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
			# filename  = f"capture_{timestamp}.mp4"
			filename = f"capture.mp4"
			video_writer = cv2.VideoWriter(
				filename, fourcc, CAPTURE_FPS, (w, h)
			)
			print(f"Recording to {filename} @ {CAPTURE_FPS} FPS...")

		# grab the union region
		frame = np.array(sct.grab(union_rect))
		if i == 0:
			cv2.imwrite("first_frame.png", frame[..., :3])

		# MSS gives BGRA; drop alpha and convert to BGR
		bgr = cv2.cvtColor(frame[..., :3], cv2.COLOR_RGB2BGR)
		video_writer.write(bgr)

		time.sleep(CAPTURE_INTERVAL)
		i += 1
		print(f"Captured frame {i}...")

	print("Stopping capture...")
	if video_writer:
		video_writer.release()
		print("Recording finished and file closed.")

if __name__ == "__main__":
	capture_loop()
