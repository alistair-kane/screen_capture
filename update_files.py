import os

def update_file_names(output: str):
	files = os.listdir(output)
	for i, file_name in enumerate(files):
		if file_name.endswith('.mp4'):
			# print(f"Renaming file: {file_name} {i+1}/{len(files)}")
			file_path = os.path.join(output, file_name)
			size = os.path.getsize(file_path)
			size_mb = size / (1024 * 1024)
			size_str = f'{size_mb:.1f}MB'
			new_file_name = f"{size_str}_{file_name}"
			new_file_path = os.path.join(output, new_file_name)
			os.rename(file_path, new_file_path)