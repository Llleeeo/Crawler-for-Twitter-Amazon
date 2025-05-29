# ====================
# 第二部分：使用Cookies自动化爬取
# ====================
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import xlwt
import json
import time
import random

def load_cookies(driver):
    """加载存储的Cookies"""
    driver.get("https://twitter.com")  # 必须先访问域名
    time.sleep(2)
    
    with open("twitter_cookies.json", "r") as f:
        cookies = json.load(f)
    
    for cookie in cookies:
        driver.add_cookie(cookie)
    
    driver.refresh()
    time.sleep(3)
    print("Cookies加载成功！")

def get_tweet_data(html, seen_tweets):
    """解析推文数据并返回新数据及更新后的已见集合"""
    soup = BeautifulSoup(html, 'html.parser')
    tweets = soup.find_all('article')  # 修正后的选择器
    datalist = []
    
    for tweet in tweets:
        try:
            # 获取推文唯一ID
            tweet_id_tag = tweet.find('a', {'href': lambda x: x and '/status/' in x})
            tweet_id = tweet_id_tag['href'].split('/')[-1] if tweet_id_tag else None

            if not tweet_id or tweet_id in seen_tweets:
                continue
            seen_tweets.add(tweet_id)

            data = []

            # 用户名
            username_div = tweet.find('div', {'data-testid': 'User-Name'})
            username = username_div.text.strip() if username_div else "N/A"
            data.append(username)

            # 内容
            content_div = tweet.find('div', {'data-testid': 'tweetText'})
            content = content_div.text.strip() if content_div else "N/A"
            data.append(content)

            # 时间
            time_tag = tweet.find('time')
            timestamp = time_tag['datetime'] if time_tag else ""
            data.append(timestamp)

            # 互动数据
            interactions = tweet.find_all('span', {'data-testid': True})
            replies = interactions[0].text if len(interactions) > 0 else "0"
            retweets = interactions[1].text if len(interactions) > 1 else "0"
            likes = interactions[2].text if len(interactions) > 2 else "0"
            data.extend([replies, retweets, likes])

            datalist.append(data)
            print("实时抓取到推文:", data)  # 实时打印
        except Exception as e:
            print(f"解析推文时出错: {str(e)}")
            continue
    
    return datalist, seen_tweets

def save_data(datalist, filename):
    """保存到Excel"""
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Twitter数据")
    
    # 设置列标题
    headers = ["用户名", "内容", "发布时间", "回复数", "转发数", "点赞数"]
    for col, header in enumerate(headers):
        sheet.write(0, col, header)
    
    # 写入数据
    for row, data in enumerate(datalist, 1):
        for col, value in enumerate(data):
            sheet.write(row, col, value)
    
    workbook.save(filename)
    print(f"数据已保存到 {filename}")

def main():
    # 浏览器配置
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # 加载Cookies
        load_cookies(driver)
        
        # 验证登录状态
        driver.get("https://twitter.com/home")
        time.sleep(3)
        print("successfully log in!!")

        # 搜索目标内容
        search_url = "https://twitter.com/search?q=smoke&src=typed_query"
        driver.get(search_url)
        time.sleep(5)  # 增加初始加载等待

        datalist = []
        seen_tweets = set()

        # 循环控制参数
        max_scroll_times = 100       # 设定最大滚动次数
        no_new_data_count = 0        # 连续无新推文的次数
        max_no_new_rounds = 3        # 允许连续无新推文次数

        while max_scroll_times > 0:
            old_len = len(datalist)

            # 向下滚动
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)

            # 动态等待
            load_time = random.uniform(5,8)  # 随机等待时间
            print(f"等待页面加载 {load_time:.1f}秒")
            time.sleep(load_time)

            # 解析新数据
            html = driver.page_source
            new_data, seen_tweets = get_tweet_data(html, seen_tweets)
            datalist.extend(new_data)

            new_len = len(datalist)
            print(f"本轮新增推文 {new_len - old_len} 条，已累计抓取 {new_len} 条推文\n")

            if new_len == old_len:
                no_new_data_count += 1
                print(f"第 {no_new_data_count} 次未发现新推文")
                if no_new_data_count >= max_no_new_rounds:
                    print(f"连续 {no_new_data_count} 次滚动没有新推文，终止爬取")
                    break
            else:
                no_new_data_count = 0

            max_scroll_times -= 1

        # 保存结果
        if datalist:
            save_data(datalist, "twitter_data.xls")
        else:
            print("未抓取到有效数据，请检查元素选择器")
            
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
    finally:
        driver.quit()

# ====================
# 执行流程控制
# ====================
if __name__ == "__main__":
    # 如果需要先保存Cookies就取消注释以下调用 (需要手动登录过程)
    # def save_twitter_cookies():
    #     driver = webdriver.Chrome()
    #     driver.get("https://twitter.com")
    #     input("请手动登录后按回车保存cookies...")
    #     with open("twitter_cookies.json", "w") as f:
    #         json.dump(driver.get_cookies(), f)
    #     driver.quit()
    # save_twitter_cookies()
    
    main()
