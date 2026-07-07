from internetarchive import get_item
from internetarchive import search_items 

item = get_item('IsaacAsimovAudioBookCollection')
print(f'Item Exists: {item.exists}')

#mp3_files = list(item.get_files(formats=['VBR MP3']))

mp3_glob = "1950 - I, Robot (Askey) 64k 06.51.45 {192mb}/1[0-3]*.mp3"

item.download(
        glob_pattern=mp3_glob,
        destdir="Asimov_Downloads",
        verbose=True,
        no_directory=True  # Keeps the folder hierarchy clean inside your destination directory
    )