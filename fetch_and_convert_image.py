import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import random
import os

# 目标网站的 URL
base_url = "https://pic.netbian.com"

# 抓取网页内容
def fetch_page_content(url):
    response = requests.get(url)
    response.encoding = 'gbk'  # 设置编码为 gbk，因为该网站使用的是 gbk 编码
    return response.text

# 解析网页内容，提取图片 URL
def extract_image_urls(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    image_tags = soup.find_all('img')
    image_urls = [img['src'] for img in image_tags if 'src' in img.attrs]
    return image_urls

# 下载图片并转换为 PNG 格式
def download_and_convert_image(image_url):
    response = requests.get(base_url + image_url)
    if response.status_code == 200:
        image_data = BytesIO(response.content)
        image = Image.open(image_data)
        png_path = "img.png"
        image.save(png_path, "PNG")
        print(f"图片已成功转换并保存为 {png_path}")
    else:
        print(f"请求图片失败，状态码: {response.status_code}")

# 主函数
def main():
    page_content = fetch_page_content(base_url)
    image_urls = extract_image_urls(page_content)
    if image_urls:
        random_image_url = random.choice(image_urls)
        download_and_convert_image(random_image_url)
    else:
        print("未找到图片 URL")

if __name__ == "__main__":
    main()