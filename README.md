# Bing-Creator-Image-Downloader
Downloads all Bing Creator images from a collection

### Prerequisites
* [Python 3.10+](https://www.python.org/downloads/)

### How to use
* Clone the repository or download and unzip
* Go to https://www.bing.com/saves?&FORM=SAVBIC&collId=3
* Select a single image from the collection
* Click `select all` in the ribbon that appears
* Click `Copy items to clipboard`
* Paste the content to the `images_clipboard.txt` file
* Navigate to the folder of the repository
* Open a terminal e.g. PowerShell
* Run `pip install -r .\requirements.txt` to install all dependencies (You may need to add the `PythonXX\Scripts` folder to your PATH first)
* Run `python .\main.py` afterward to run the script 
* The images of the collection are saved in the `bing_images_$TodaysDate.zip` file

### Addendum
It should take about ~30-60 seconds to download 1500 images from my testing.  
Each image contains the original prompt and image link as EXIF Metadata in the `UserComment` field in a JSON format.  
If you encounter any errors or warnings in your log, please open a new issue.