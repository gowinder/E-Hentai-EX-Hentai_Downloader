import os
import shutil
import zipfile


def get_zip_filename_by_dir(folder_path):
    zip_filename = "%s.zip" % folder_path
    return zip_filename

def make_zip(folder_path, remove=True):
    zip_filename = get_zip_filename_by_dir(folder_path)
    if os.path.exists(zip_filename):
        return zip_filename
    with zipfile.ZipFile(zip_filename, 'w', allowZip64=True) as zipFile:
        for f in sorted(os.listdir(folder_path)):
            fullpath = os.path.join(folder_path, f)
            zipFile.write(fullpath, f, zipfile.ZIP_STORED)
    if remove:
        shutil.rmtree(folder_path)
    return zip_filename
