import os
import time
import random
import uuid
import logging
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from PIL import Image
from io import BytesIO
from bs4 import BeautifulSoup
import xlwt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('imdb_scraper.log'),
        logging.StreamHandler()
    ]
)

# 创建图片保存目录
image_dir = 'imdb_movie_posters'
if not os.path.exists(image_dir):
    os.makedirs(image_dir)
    logging.info(f"创建图片保存目录: {image_dir}")

# 设置请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.imdb.com/',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache'
}


class WorkTimer:
    """工作时间计时器，只计算实际工作时间"""

    def __init__(self):
        self.total_time = 0.0
        self._start_time = None
        self.is_running = False

    def start(self):
        """开始计时"""
        if not self.is_running:
            self._start_time = time.time()
            self.is_running = True

    def pause(self):
        """暂停计时"""
        if self.is_running and self._start_time is not None:
            self.total_time += time.time() - self._start_time
            self.is_running = False

    def resume(self):
        """恢复计时"""
        if not self.is_running:
            self._start_time = time.time()
            self.is_running = True

    def stop(self):
        """停止计时并返回总工作时间"""
        if self.is_running and self._start_time is not None:
            self.total_time += time.time() - self._start_time
            self.is_running = False
        return self.total_time

    def get_elapsed_time(self):
        """获取当前工作时间（不停止计时）"""
        if self.is_running and self._start_time is not None:
            return self.total_time + (time.time() - self._start_time)
        return self.total_time


def setup_driver():
    """配置和初始化Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1400,900")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--lang=en-US")

    # 设置用户代理
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    chrome_options.add_argument(f'user-agent={user_agent}')

    # 初始化WebDriver
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except WebDriverException as e:
        logging.error(f"WebDriver初始化失败: {str(e)}")
        raise


def download_single_image(img_url, movie_title, timer, max_retries=3):
    """下载并保存单个电影海报"""
    timer.start()  # 开始计时
    for attempt in range(max_retries):
        try:
            response = requests.get(img_url, headers=HEADERS, timeout=10)
            response.raise_for_status()

            # 检查图片格式
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                logging.warning(f"URL不是图片: {img_url} (Content-Type: {content_type})")
                timer.pause()  # 暂停计时
                return None

            # 打开图片并保存
            image = Image.open(BytesIO(response.content))

            # 生成文件名（使用电影标题）
            safe_title = "".join(c if c.isalnum() else "_" for c in movie_title)[:50]
            filename = f"{safe_title}_{uuid.uuid4().hex[:4]}.jpg"
            filepath = os.path.join(image_dir, filename)

            # 保存为JPEG
            image.save(filepath, "JPEG")
            logging.info(f"海报下载成功: {filename} ({movie_title})")
            timer.pause()  # 暂停计时
            return filepath
        except requests.exceptions.RequestException as e:
            logging.warning(f"海报下载失败 (尝试 {attempt + 1}/{max_retries}): {movie_title} - {str(e)}")
            timer.pause()  # 暂停计时
            time.sleep(random.uniform(1, 3))  # 等待时间不计时
            timer.resume()  # 恢复计时
        except Exception as e:
            logging.error(f"处理海报时出错: {movie_title} - {str(e)}")
            timer.pause()  # 暂停计时
            break

    timer.pause()  # 暂停计时
    return None


def scroll_to_load_more(driver, timer, max_scrolls=15):
    """滚动页面以加载更多内容"""
    logging.info("开始滚动页面以加载所有电影...")

    # 滚动到页面底部多次
    for scroll_count in range(1, max_scrolls + 1):
        timer.start()  # 开始计时
        # 滚动到页面底部
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
        logging.info(f"执行滚动 #{scroll_count}")
        timer.pause()  # 暂停计时

        # 随机等待时间 (模拟人类浏览，不计时)
        wait_time = random.uniform(1.5, 3.5)
        time.sleep(wait_time)

        # 检查是否已加载所有内容（实际工作，计时）
        timer.start()  # 开始计时
        try:
            end_indicator = driver.find_element(By.CSS_SELECTOR, "div.ipc-error-message")
            if end_indicator and "No results found" in end_indicator.text:
                logging.info("已加载所有电影内容")
                timer.pause()  # 暂停计时
                break
        except:
            pass
        timer.pause()  # 暂停计时

    logging.info("页面滚动完成")


def extract_movie_data(driver, timer):
    """从页面提取电影数据"""
    timer.start()  # 开始计时
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    movies = []

    # 查找所有电影条目
    movie_items = soup.select('li.ipc-metadata-list-summary-item')
    logging.info(f"找到 {len(movie_items)} 部电影")

    for item in movie_items:
        try:
            movie_data = {}

            # 提取排名
            rank_element = item.select_one('div.ipc-title__text')
            if rank_element:
                rank_text = rank_element.text.strip()
                if '.' in rank_text:
                    movie_data['rank'] = rank_text.split('.')[0].strip()
                else:
                    movie_data['rank'] = "N/A"

            # 提取标题
            title_element = item.select_one('a[href*="/title/"]')
            if title_element:
                movie_data['title'] = title_element.text.strip()
                movie_data['url'] = "https://www.imdb.com" + title_element['href']
            else:
                movie_data['title'] = "N/A"
                movie_data['url'] = "N/A"

            # 提取年份
            year_element = item.select_one('span.cli-title-metadata-item')
            if year_element:
                movie_data['year'] = year_element.text.strip()
            else:
                movie_data['year'] = "N/A"

            # 提取评分
            rating_element = item.select_one('span.ipc-rating-star')
            if rating_element:
                rating_text = rating_element.text.strip()
                movie_data['rating'] = rating_text.split()[0] if rating_text else "N/A"
            else:
                movie_data['rating'] = "N/A"

            # 提取海报URL
            poster_element = item.select_one('img.ipc-image')
            if poster_element:
                poster_url = poster_element.get('src') or poster_element.get('data-src')
                # 获取更高分辨率的图片
                if poster_url and '@._' in poster_url:
                    poster_url = poster_url.split('@._')[0] + '@._V1_QL75_UX380_CR0,0,380,562_.jpg'
                movie_data['poster_url'] = poster_url
            else:
                movie_data['poster_url'] = "N/A"

            # 提取类型和时长
            metadata_items = item.select('span.cli-title-metadata-item')
            if len(metadata_items) >= 2:
                movie_data['duration'] = metadata_items[1].text.strip()
            else:
                movie_data['duration'] = "N/A"

            # 提取演员
            cast_element = item.select_one('div.ipc-title__subtext')
            if cast_element:
                movie_data['cast'] = cast_element.text.strip()
            else:
                movie_data['cast'] = "N/A"

            movies.append(movie_data)
            logging.info(f"提取电影: {movie_data['rank']}. {movie_data['title']} ({movie_data['year']})")

        except Exception as e:
            logging.error(f"提取电影数据时出错: {str(e)}")
            continue

    timer.pause()  # 暂停计时
    return movies


def save_data_to_excel(movies, filename, timer):
    """将电影数据保存到Excel"""
    timer.start()  # 开始计时
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("IMDb Top Action Movies")

    # 设置列标题
    headers = ["排名", "标题", "年份", "评分", "时长", "演员", "海报URL", "电影URL"]
    for col, header in enumerate(headers):
        sheet.write(0, col, header)

    # 设置列宽
    sheet.col(0).width = 2000  # 排名
    sheet.col(1).width = 10000  # 标题
    sheet.col(2).width = 2000  # 年份
    sheet.col(3).width = 2000  # 评分
    sheet.col(4).width = 4000  # 时长
    sheet.col(5).width = 15000  # 演员
    sheet.col(6).width = 15000  # 海报URL
    sheet.col(7).width = 15000  # 电影URL

    # 写入数据
    for row, movie in enumerate(movies, 1):
        sheet.write(row, 0, movie.get('rank', 'N/A'))
        sheet.write(row, 1, movie.get('title', 'N/A'))
        sheet.write(row, 2, movie.get('year', 'N/A'))
        sheet.write(row, 3, movie.get('rating', 'N/A'))
        sheet.write(row, 4, movie.get('duration', 'N/A'))
        sheet.write(row, 5, movie.get('cast', 'N/A'))
        sheet.write(row, 6, movie.get('poster_url', 'N/A'))
        sheet.write(row, 7, movie.get('url', 'N/A'))

    workbook.save(filename)
    logging.info(f"电影数据已保存到 {filename}")
    timer.pause()  # 暂停计时


def main():
    # 初始化工作时间计时器
    timer = WorkTimer()

    # 初始化WebDriver
    logging.info("初始化浏览器...")
    timer.start()  # 开始计时
    driver = setup_driver()
    timer.pause()  # 暂停计时

    # 目标URL
    target_url = "https://www.imdb.com/chart/top/?ref_=nv_mv_250&genres=action"

    try:
        # 访问目标URL
        logging.info(f"访问URL: {target_url}")
        timer.start()  # 开始计时
        driver.get(target_url)

        # 等待页面加载
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item"))
        )
        logging.info("页面初始加载完成")
        timer.pause()  # 暂停计时

        # 随机等待，避免被检测（不计时）
        wait_time = random.uniform(2, 4)
        time.sleep(wait_time)

        # 滚动页面以加载所有内容
        scroll_to_load_more(driver, timer)

        # 提取电影数据
        movies = extract_movie_data(driver, timer)

        if not movies:
            logging.warning("没有找到电影数据，程序退出")
            return

        # 下载电影海报
        logging.info("开始下载电影海报...")
        for movie in movies:
            poster_url = movie.get('poster_url')
            if poster_url and poster_url != "N/A":
                download_single_image(poster_url, movie['title'], timer)
            else:
                logging.warning(f"电影 '{movie['title']}' 没有可用的海报URL")

        # 保存数据到Excel
        save_data_to_excel(movies, "imdb_top_action_movies.xls", timer)

        # 获取总工作时间
        work_time = timer.stop()

        logging.info("\n" + "=" * 60)
        logging.info(f"爬取完成! 总共提取 {len(movies)} 部电影数据")
        logging.info(f"海报已保存到目录: {image_dir}")
        logging.info(f"实际工作时间: {work_time:.2f}秒 ({work_time / 60:.2f}分钟)")

    except TimeoutException:
        logging.error("页面加载超时")
        timer.stop()
    except NoSuchElementException as e:
        logging.error(f"元素未找到: {str(e)}")
        timer.stop()
    except Exception as e:
        logging.exception(f"程序运行出错: {str(e)}")
        timer.stop()
    finally:
        # 关闭浏览器
        driver.quit()
        logging.info("浏览器已关闭")


if __name__ == "__main__":
    main()
