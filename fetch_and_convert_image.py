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

# 添加新的常量
HISTORY_FILE = "used_images.txt"
IMAGE_POOL_FILE = "image_pool.json"  # 存储图片池
MAX_HISTORY = 2000
FETCH_COUNT = 200
CACHE_DIR = "cache"
POOL_UPDATE_DAYS = 30  # 图片池更新间隔（天）

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

def get_used_images() -> set:
    """获取已使用过的图片URL列表"""
    try:
        if not os.path.exists(HISTORY_FILE):
            return set()
            
        # 读取时过滤掉空行和无效URL
        with open(HISTORY_FILE, 'r') as f:
            urls = set()
            for line in f:
                url = line.strip()
                if url and url.startswith('http'):
                    urls.add(url)
            return urls
    except Exception as e:
        logger.error(f"读取历史记录失败: {str(e)}")
        return set()

def add_used_image(image_url: str):
    """添加使用过的图片URL到历史记录"""
    try:
        used_images = get_used_images()
        used_images.add(image_url)
        
        # 如果历史记录太多，保留最新的部分
        if len(used_images) > MAX_HISTORY:
            used_images = set(sorted(list(used_images))[-MAX_HISTORY:])
        
        # 原子写入，避免并发问题
        temp_file = f"{HISTORY_FILE}.tmp"
        with open(temp_file, 'w') as f:
            for url in sorted(used_images):  # 排序以保持稳定
                f.write(f"{url}\n")
        os.replace(temp_file, HISTORY_FILE)  # 原子替换
        
    except Exception as e:
        logger.error(f"保存历史记录失败: {str(e)}")

def fetch_image_urls() -> List[str]:
    """获取必应壁纸URL列表"""
    try:
        session = create_session()
        image_urls = set()
        used_images = get_used_images()
        
        # 分批获取图片，直到获取足够多的新图片
        idx = 0
        while len(image_urls) < FETCH_COUNT and idx < 365:  # 最多获取一年的图片
            params = {
                'format': 'js',
                'idx': str(idx),
                'n': '100',  # 每次获取100张
                'mkt': 'zh-CN'
            }
            
            logger.info(f"获取必应壁纸列表 (idx={idx})")
            try:
                response = session.get(BING_API_URL, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                if 'images' in data:
                    images = data['images']
                    for image in images:
                        try:
                            if 'url' in image:
                                image_url = f"{BING_URL}{image['url'].replace('1920x1080', 'UHD')}"
                                if image_url not in used_images:
                                    image_urls.add(image_url)
                                    logger.info(f"找到新图片: {image_url}")
                        except Exception as e:
                            logger.error(f"处理图片项失败: {str(e)}")
                            continue
                
                if not images:  # 如果没有更多图片了
                    break
                    
                idx += len(images)
                time.sleep(1)  # 避免请求太快
                
            except Exception as e:
                logger.error(f"获取壁纸列表失败: {str(e)}")
                break
        
        logger.info(f"总共找到 {len(image_urls)} 个新图片")
        return list(image_urls)
        
    except Exception as e:
        logger.error(f"获取图片URL失败: {str(e)}")
        return []

def validate_and_process_image(image: Image.Image) -> Optional[Image.Image]:
    """验证并处理图片，返回处理后的图片或None"""
    try:
        # 检查图片模式
        if image.mode not in ['RGB', 'RGBA']:
            image = image.convert('RGB')
        
        width, height = image.size
        ratio = width / height
        
        # 基本验证
        if width < 1920 or height < 1080:
            logger.info(f"图片尺寸不足: {width}x{height}")
            return None
            
        if not (1.5 <= ratio <= 2.5):
            logger.info(f"图片宽高比不合适: {ratio:.2f}")
            return None
        
        # 智能裁剪和缩放
        target_width = 1920
        target_height = int(target_width / ratio)
        
        # 如果图片太大，先缩小
        if width > target_width * 2:
            scale_factor = target_width / width
            new_size = (target_width, int(height * scale_factor))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"缩放图片到: {new_size}")
        
        # 增强图片质量
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)  # 轻微增强对比度
        
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.1)  # 轻微锐化
        
        return image
        
    except Exception as e:
        logger.error(f"图片处理失败: {str(e)}")
        return None

def save_optimized_image(image: Image.Image, path: str) -> bool:
    """保存优化后的图片"""
    try:
        # 使用渐进式JPEG
        image.save(path, "JPEG", 
                  quality=85, 
                  optimize=True, 
                  progressive=True)
        
        size_kb = os.path.getsize(path) / 1024
        
        # 如果文件太大，使用自适应质量
        if size_kb > 500:
            quality = 85
            while size_kb > 500 and quality > 60:
                quality -= 5
                image.save(path, "JPEG", 
                          quality=quality, 
                          optimize=True, 
                          progressive=True)
                size_kb = os.path.getsize(path) / 1024
                logger.info(f"压缩图片 (quality={quality}): {size_kb:.1f}KB")
        
        return True
        
    except Exception as e:
        logger.error(f"保存图片失败: {str(e)}")
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
        
        if not validate_and_process_image(image):
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

def should_update_pool() -> bool:
    """检查是否需要更新图片池"""
    try:
        if not os.path.exists(IMAGE_POOL_FILE):
            return True
            
        # 检查文件修改时间
        mtime = os.path.getmtime(IMAGE_POOL_FILE)
        days_old = (time.time() - mtime) / (24 * 3600)
        
        return days_old >= POOL_UPDATE_DAYS
    except Exception as e:
        logger.error(f"检查图片池状态失败: {str(e)}")
        return True

def save_image_pool(urls: List[str]):
    """保存图片池"""
    try:
        with open(IMAGE_POOL_FILE, 'w') as f:
            json.dump({'urls': urls, 'updated_at': time.time()}, f)
        logger.info(f"已更新图片池，包含 {len(urls)} 张图片")
    except Exception as e:
        logger.error(f"保存图片池失败: {str(e)}")

def load_image_pool() -> List[str]:
    """加载图片池"""
    try:
        if os.path.exists(IMAGE_POOL_FILE):
            with open(IMAGE_POOL_FILE, 'r') as f:
                data = json.load(f)
                return data.get('urls', [])
    except Exception as e:
        logger.error(f"加载图片池失败: {str(e)}")
    return []

def main():
    try:
        # 确保缓存目录存在
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        # 检查是否需要更新图片池
        if should_update_pool():
            logger.info("开始更新图片池")
            image_urls = fetch_image_urls()  # 获取新的图片列表
            if image_urls:
                save_image_pool(image_urls)
            else:
                logger.warning("获取新图片失败，尝试使用现有图片池")
        
        # 从图片池中获取图片
        image_urls = load_image_pool()
        if not image_urls:
            logger.warning("图片池为空")
            return
        
        # 随机选择并处理图片
        used_images = get_used_images()
        available_urls = [url for url in image_urls if url not in used_images]
        
        if not available_urls:
            logger.warning("没有可用的新图片")
            # 如果所有图片都用过了，清空历史记录重新开始
            open(HISTORY_FILE, 'w').close()
            available_urls = image_urls
        
        # 随机选择一张图片
        image_url = random.choice(available_urls)
        
        try:
            # 下载并处理图片
            session = create_session()
            response = session.get(image_url, timeout=10)
            response.raise_for_status()
            
            image = Image.open(BytesIO(response.content))
            processed_image = validate_and_process_image(image)
            
            if processed_image:
                if save_optimized_image(processed_image, "img.jpg"):
                    add_used_image(image_url)
                    logger.info("成功更新壁纸")
                    return
                    
        except Exception as e:
            logger.error(f"处理图片失败: {str(e)}")
        
        logger.warning("更新壁纸失败")
        
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")

if __name__ == "__main__":
    main()