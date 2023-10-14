# Bing-Creator-Image-Downloader
Downloads all Bing Creator images from a collection

### Prerequisites
* [Python](https://www.python.org/downloads/)
* [Gecko driver](https://github.com/mozilla/geckodriver/releases)

### How to use
* Clone the repository or download and unzip
* Change the variable `gecko_path` to the path of the folder where you extracted the gecko driver
* Go to https://www.bing.com/saves?&FORM=SAVBIC&collId=3
* Select a single image from the collection
* Click `select all` in the ribbon that appears
* Click `Copy items to clipboard`
* Paste the content to the `images_clipboard.txt` file
* Navigate to the folder of the repository
* Open a terminal e.g. PowerShell
* Run `pip install -r .\requirements.txt` to install all dependencies (You may need to add the `PythonXX\Scripts` folder to your PATH first)
* Run `python .\main.py` afterwards to run the script 
* The images of the collection are saved in the `bing_images_$TodaysDate.zip` file

### Disclaimer
Because of how the images are accessed there may be some images that are duplicated or images that appear that weren't in the text file.  
This is due to some specific images being "bugged" in a way.  
I'm still investigating this issue.  
You can try it yourself with this image link:  
https://www.bing.com/images/create/smiling-broccoli-clip-art/652183e34a724d468a349fb18b529630?id=hEG1qCC3aSwVQ%2fyFKw4zNw%3d%3d&view=detailv2&idpp=genimg  
This issue occurs more often when you have images that were in the same generation run (4 images with the same prompt).  