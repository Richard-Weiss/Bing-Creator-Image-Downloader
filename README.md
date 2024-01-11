# Bing-Creator-Image-Downloader
Downloads all Bing Creator images from a collection

### Prerequisites
* [Python 3.11+](https://www.python.org/downloads/)

### How to use
* Clone the repository or download and unzip
#### Collection API method:
* Get your `_U` cookie for Bing. For example like described in this [comment](https://old.reddit.com/r/bing/comments/172rpo6/is_there_any_way_to_download_image_collections/k72vjqs/) or this [package](https://pypi.org/project/sydney-py/)
* Paste the value after the equals sign for the `_U` property in the `COOKIE` property in the `.env.example` file.
* Add your own collections to the `collections_to_include` property in the `config.toml` or leave the array empty to download for all collections
* Rename the `.env.example` file to `.env`
#### Clipboard file method:
* Go to the collection you want to download at https://www.bing.com/saves
* Scroll down until all images are loaded
* Click the `Select all results in this collection button`
* Click the `Copy items to clipboard button`
* Wait until all images are copied to the clipboard (it may take a while)
* Paste the clipboard content into the `images_clipboard.txt.example` file
* Remove the `.example` from the file name so it's called `images_clipboard.txt`
#### Shared next steps:
* Check in the `config.toml` if the correct image source method is selected
* Navigate to the folder of the repository
* Open a terminal e.g. PowerShell
* Run `pip install -r .\requirements.txt` to install all dependencies (You may need to add the `PythonXX\Scripts` folder to your PATH first)
* Run `python .\main.py` afterward to run the script 
* The images of the collection are saved in the `bing_images_$TodaysDate.zip` file

### Addendum
Each image contains the original prompt, used image link and creation date as EXIF Metadata in the `UserComment` field in a JSON format.  
It is also saved in the XPComment field, so you can view and edit it directly in the Windows Explorer.  
If you encounter any errors or have some requests, please open a new issue or discussion.
