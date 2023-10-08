import os
import requests
import zipfile

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec


def get_image_tuples(img_url_list: list):
    options = Options()
    options.add_argument("-headless")
    service = Service(gecko_path)
    driver = webdriver.Firefox(options=options, service=service)
    img_tuples = []
    for url in img_url_list:
        driver.get(url)
        img = WebDriverWait(driver, 10).until(
            ec.presence_of_element_located((By.XPATH, "//div[@class='imgContainer']/img"))
        )
        img_tuples.append(
            (img.get_attribute("src"), img.get_attribute("alt"))
        )
    driver.quit()
    os.remove("geckodriver.log")
    return img_tuples


if __name__ == "__main__":
    gecko_path = "C:\\Users\\icepe\\Developer_Tools\\Gecko Driver"

    with open("images_clipboard.txt", "r") as f:
        content = f.read().splitlines()
    lines = [line for line in content if line != "www.bing.com" and line != ""]
    image_url_list = [lines[i + 1] for i in range(0, len(lines), 2)]
    image_tuples = get_image_tuples(image_url_list)
    zip_file = zipfile.ZipFile("bing_images.zip", "w")

    for index, (src, alt) in enumerate(image_tuples):
        try:
            response = requests.get(src)
            if response.status_code == 200:
                filename = f"{alt}_{str(index)}.jpg"
                with open(filename, "wb") as f:
                    f.write(response.content)
                zip_file.write(filename)
                os.remove(filename)
            else:
                print(f"Failed to download {src}")
        except Exception as e:
            print(e)

    zip_file.close()
