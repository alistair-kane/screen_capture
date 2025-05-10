import numpy as np
import Quartz as QZ

class WindowCapture:

	# properties
	window_name = None
	window = None
	window_id = None
	window_width = 0
	window_height = 0

	def __init__(self, given_window_name=None):
		if given_window_name is not None:

			self.window_name = given_window_name
			self.window = self.get_window()

			if self.window is None:
				raise Exception('Unable to find window: {}'.format(given_window_name))

			self.window_id = self.get_window_id()

			self.window_width = self.get_window_width()
			self.window_height = self.get_window_height()

			self.window_x = self.get_window_pos_x()
			self.window_y = self.get_window_pos_y()
		else:
			raise Exception('No window name given')

	def get_window(self):
		windows = QZ.CGWindowListCopyWindowInfo(QZ.kCGWindowListOptionAll, QZ.kCGNullWindowID)
		for window in windows:
			name = window.get('kCGWindowName', 'Unknown')
			# if name:
				# print('Window name: {}'.format(name))
			if name and self.window_name in name:
				return window
		return None
	
	def get_window_id(self):
		return self.window['kCGWindowNumber']

	def get_window_width(self):
		return int(self.window['kCGWindowBounds']['Width'])
	
	def get_window_height(self):
		return int(self.window['kCGWindowBounds']['Height'])

	def get_window_pos_x(self):
		return int(self.window['kCGWindowBounds']['X'])

	def get_window_pos_y(self):
		return int(self.window['kCGWindowBounds']['Y'])
	
	def get_image_from_window(self):
		core_graphics_image = QZ.CGWindowListCreateImage(
			QZ.CGRectNull,
			QZ.kCGWindowListOptionIncludingWindow,
			self.window_id,
			QZ.kCGWindowImageBoundsIgnoreFraming | QZ.kCGWindowImageNominalResolution
		)

		bytes_per_row = QZ.CGImageGetBytesPerRow(core_graphics_image)
		width = QZ.CGImageGetWidth(core_graphics_image)
		height = QZ.CGImageGetHeight(core_graphics_image)

		core_graphics_data_provider = QZ.CGImageGetDataProvider(core_graphics_image)
		core_graphics_data = QZ.CGDataProviderCopyData(core_graphics_data_provider)

		np_raw_data = np.frombuffer(core_graphics_data, dtype=np.uint8)

		numpy_data = np.lib.stride_tricks.as_strided(np_raw_data,
												shape=(height, width, 3),
												strides=(bytes_per_row, 4, 1),
												writeable=False)
		
		final_output = np.ascontiguousarray(numpy_data, dtype=np.uint8)

		return final_output
	
	# def get_regions(self, h_regions, v_regions):
	# 	# Calculate the width and height of each region
	# 	region_width = self.window_width // v_regions
	# 	region_height = self.window_height // h_regions
	# 	regions = []
	# 	for i in range(h_regions):
	# 		for j in range(v_regions):
	# 			y = int(i * region_height)
	# 			x = int(j * region_width)
	# 			w = int(region_width)
	# 			h = int(region_height)
	# 			regions.append((x, y, w, h))
	# 	return regions