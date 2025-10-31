import io
import os
import zipfile


def zip_directory(path: str):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=path)
                zipf.write(file_path, arcname)

    zip_buffer.seek(0)
    return zip_buffer
