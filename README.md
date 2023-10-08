# Bing-Creator-Image-Downloader
Downloads all Bing Creator images from a collection

### Prerequisites
* Python 3.8
* Gecko driver

### How to use
* Change the variable `gecko_path` to the path of the folder where you extracted the gecko driver
* Go to https://www.bing.com/saves?&FORM=SAVBIC&collId=3
* Select a single image from the collection
* Click `select all` in the ribbon that appears
* Click `Copy items to clipboard`
* Paste the content to the `images_clipboard.txt` file
* Execute the script and wait 2-3 seconds per image for all images to download
* The images of the collection are saved in the `bing_images.zip` file