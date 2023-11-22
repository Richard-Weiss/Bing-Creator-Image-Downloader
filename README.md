# Bing-Creator-Image-Downloader
Downloads all Bing Creator images from a collection

### Prerequisites
* [Python 3.11+](https://www.python.org/downloads/)

### How to use
* Clone the repository or download and unzip
* Get your `_U` cookie for Bing. For example like described in this [comment](https://old.reddit.com/r/bing/comments/172rpo6/is_there_any_way_to_download_image_collections/k72vjqs/) or this [package](https://pypi.org/project/sydney-py/)
* Paste the value after the equals sign for the `_U` property in the `COOKIE` property in the `.env.example` file.
* Add your own collections to the `collections_to_include` property in the `config.toml` or leave the property completely empty to download for all collections
* Rename the `.env.example` file to `.env`
* Navigate to the folder of the repository
* Open a terminal e.g. PowerShell
* Run `pip install -r .\requirements.txt` to install all dependencies (You may need to add the `PythonXX\Scripts` folder to your PATH first)
* Run `python .\main.py` afterward to run the script 
* The images of the collection are saved in the `bing_images_$TodaysDate.zip` file

### Addendum
It should take about ~30-90 seconds to download 1500 images from my testing.  
Each image contains the original prompt and image link as EXIF Metadata in the `UserComment` field in a JSON format.
If you encounter any errors or warnings in your log, please open a new issue.