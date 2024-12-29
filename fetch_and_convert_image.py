import requests
from PIL import Image
from io import BytesIO
import random
import os
import time
import urllib3
from typing import List, Optional, Dict
import logging
import json  # 替换 bs4，使用内置的 json 模块

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 网站配置
BING_URL = "https://www.bing.com"
BING_API_URL = "https://www.bing.com/HPImageArchive.aspx"

def get_headers() -> Dict[str, str]:
    """获取请求头"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }

def create_session() -> requests.Session:
    """创建一个带有重试机制的会话"""
    session = requests.Session()
    session.headers.update(get_headers())
    
    # 配置重试机制
    retry_strategy = urllib3.util.Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def fetch_image_urls() -> List[str]:
    """获取必应壁纸URL列表"""
    try:
        session = create_session()
        image_urls = set()
        
        # 获取最近8天的壁纸
        params = {
            'format': 'js',  # 返回JSON格式
            'idx': '0',      # 从今天开始
            'n': '8',        # 获取8张图片
            'mkt': 'zh-CN'   # 中国区域
        }
        
        logger.info("获取必应壁纸列表")
        try:
            response = session.get(BING_API_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'images' in data:
                images = data['images']
                logger.info(f"找到 {len(images)} 个壁纸")
                
                # 随机打乱图片顺序
                random.shuffle(images)
                
                for image in images:
                    try:
                        # 获取原图URL
                        if 'url' in image:
                            # 构建UHD图片URL
                            image_url = f"{BING_URL}{image['url'].replace('1920x1080', 'UHD')}"
                            image_urls.add(image_url)
                            logger.info(f"找到原图: {image_url}")
                        
                        if len(image_urls) >= 3:
                            break
                            
                    except Exception as e:
                        logger.error(f"处理图片项失败: {str(e)}")
                        continue
            
        except Exception as e:
            logger.error(f"获取壁纸列表失败: {str(e)}")
            if 'response' in locals():
                logger.debug(f"响应内容: {response.text[:500]}")
        
        logger.info(f"总共找到 {len(image_urls)} 个图片")
        return list(image_urls)
        
    except Exception as e:
        logger.error(f"获取图片URL失败: {str(e)}")
        return []

def validate_image(image: Image.Image) -> bool:
    """验证图片是否满足要求"""
    min_width = 1920
    min_height = 1080
    min_ratio = 1.5
    max_ratio = 2.5
    target_size_mb = 0.5  # 目标文件大小为 500KB
    
    try:
        # 检查图片模式
        if image.mode not in ['RGB', 'RGBA']:
            logger.info(f"不支持的图片模式: {image.mode}")
            image = image.convert('RGB')
        
        width, height = image.size
        ratio = width / height
        
        # 检查分辨率
        if width < min_width or height < min_height:
            logger.info(f"图片尺寸不足: {width}x{height}, 需要至少 {min_width}x{min_height}")
            return False
        
        # 检查宽高比
        if ratio < min_ratio or ratio > max_ratio:
            logger.info(f"图片宽高比不合适: {ratio:.2f}, 需要在 {min_ratio} 到 {max_ratio} 之间")
            return False
        
        # 调整图片大小到合适的分辨率
        target_width = 1920
        target_height = int(target_width / ratio)
        if width > target_width:
            logger.info(f"调整图片大小到 {target_width}x{target_height}")
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        return True
        
    except Exception as e:
        logger.error(f"图片验证失败: {str(e)}")
        return False

def download_and_convert_image(image_url: str) -> bool:
    """下载并转换图片，返回是否成功"""
    headers = get_headers()
    
    try:
        session = create_session()
        logger.info(f"下载图片: {image_url}")
        response = session.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        image = Image.open(BytesIO(response.content))
        logger.info(f"原始图片尺寸: {image.size}")
        
        if not validate_image(image):
            return False
            
        # 保存为 JPEG 格式，使用适当的压缩
        jpg_path = "img.jpg"
        image.save(jpg_path, "JPEG", quality=85, optimize=True)
        
        if os.path.exists(jpg_path) and os.path.getsize(jpg_path) > 0:
            size_kb = os.path.getsize(jpg_path) / 1024
            logger.info(f"图片已成功保存: {jpg_path} ({size_kb:.1f}KB)")
            
            # 如果文件仍然太大，继续压缩
            if size_kb > 500:  # 如果大于 500KB
                quality = 85
                while size_kb > 500 and quality > 60:
                    quality -= 5
                    image.save(jpg_path, "JPEG", quality=quality, optimize=True)
                    size_kb = os.path.getsize(jpg_path) / 1024
                    logger.info(f"重新压缩图片 (quality={quality}): {size_kb:.1f}KB")
            
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"处理图片失败: {str(e)}")
        return False

def main():
    try:
        image_urls = fetch_image_urls()
        if not image_urls:
            logger.warning("未找到任何图片")
            return
            
        # 随机尝试最多3个图片URL
        random.shuffle(image_urls)
        for image_url in image_urls[:3]:
            if download_and_convert_image(image_url):
                return
            time.sleep(2)
        
        logger.warning("所有尝试都失败")
        
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")

if __name__ == "__main__":
    main()