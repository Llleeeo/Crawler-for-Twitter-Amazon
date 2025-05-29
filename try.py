from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import xlwt
import json
import time
import random

# ====================
# 第一部分：存储Cookies
# ====================
def save_twitter_cookies():
    # 配置浏览器选项
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver = webdriver.Chrome(options=options)
    driver.get("https://twitter.com/login")
    
    # 等待用户手动登录
    print("请在浏览器中完成登录操作...")
    input("登录完成后，按回车键继续 >>> ")
    
    # 保存Cookies
    cookies = driver.get_cookies()
    with open("twitter_cookies.json", "w") as f:
        json.dump(cookies, f)
    
    driver.quit()
    print("Cookies已成功保存到twitter_cookies.json")

save_twitter_cookies()