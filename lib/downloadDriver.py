import subprocess

import json2
from win32com.client import Dispatch
import re
import stat,zipfile,os,psutil
import requests
from requests.packages import urllib3
urllib3.disable_warnings()
from lxml import etree
import time

class auto_download_chromedrive(object):
    def __init__(self):
        self.chromedrive_url = "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json"
        self.local_chrome_paths = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                                   r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]

        self.headers = {'content-type': 'application/json',
                        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}
    def get_version_via_com(self, filename):
        parser = Dispatch("Scripting.FileSystemObject")
        try:
            version = parser.GetFileVersion(filename)
        except Exception:
            return None
        return version
    def get_chromedriver_urls(self):
        try:
            r = requests.Session()
            response = r.get(self.chromedrive_url, headers=self.headers,verify=False,proxies={"http":"127.0.0.1:7980"})
            # print(response.status_code, response.encoding)
            parsed_data = json2.loads(response.text)
            version_href={}
            # 提取每个版本中 ChromeDriver Windows 32 的链接
            for milestone, info in parsed_data['milestones'].items():
                downloads = info.get('downloads', {})
                if 'chromedriver' in downloads:
                    for driver in info['downloads']['chromedriver']:
                        if driver['platform'] == 'win32':
                            # print(f"Version {milestone}: {driver['url']}")
                            version_href[milestone]=driver['url']
            # print(version_href)
            return version_href
        except Exception:
            return None
    def download_chromadrive(self, url):
        try:
            r = requests.Session()
            response = r.get(url, headers=self.headers,verify=False,proxies={"http":"127.0.0.1:7980"})
            if response.status_code == 200:
                with open("chromedriver_win32.zip", "wb") as f:
                    f.write(response.content)
                    print("下载完成")
                    return 1
            else:
                print('Url请求返回错误，错误码为： %d' % response.status_code)
                return None
        except Exception:
            print("request download chromedriver_win32.zip failed!")
            return None
    def find_local_version(self, loc_ver, all_ver):
        """
        :param loc_ver: 本地浏览器的版本
        :param all_ver: 下载的所有版本浏览器版本
        :return: 找到匹配的，return url,否则return None
        """
        try:
            if loc_ver in all_ver:
                return loc_ver
        except Exception as e:
            print(e)

        print("not find match chrome browser{} version!".format(loc_ver))
        return None
    def kill_process(self, process_name):
        print("检测{}进程是否存在，存在则杀掉。".format(process_name))
        pl = psutil.pids()
        for pid in pl:
            if psutil.Process(pid).name() == process_name:
                print('{} 存在进程中,杀掉'.format(process_name))
                os.popen('taskkill /f /im %s' %process_name)
                return pid
        print('{} 不存在进程中。'.format(process_name))
        return None

    def unzip(self):
        self.kill_process("chromedriver.exe")
        print("去除旧版本chromedriver_win32文件夹内文件的只读属性(如果是只读)")
        old_driver_path = os.path.join(os.getcwd(), "chromedriver_win32")
        if os.path.exists(old_driver_path):
            for sub_file in os.listdir(old_driver_path):
                os.chmod(os.path.join(old_driver_path, sub_file), stat.S_IRWXU)
        time.sleep(1) #这个delay必须要有，os操作还是需要时间的
        print('''解压 chromedriver_win32.zip,覆盖旧版本''')
        zFile = zipfile.ZipFile(os.path.join(os.getcwd(), "chromedriver_win32.zip"), "r")
        for fileM in zFile.namelist():
            zFile.extract(fileM, old_driver_path)
        zFile.close()

    def get_chromedriver_version(self,path):
        try:
            output = subprocess.check_output([path, '--version'])
            version = output.strip()
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)', version)
            if match:
                return match.group(1).split(".")[0]
            return None
        except Exception as e:
            return f"Error: {e}"

    def start_(self,version,version_href):
        find_version = self.find_local_version(version.split(".")[0], version_href)
        print("找到匹配的版本:\n%s" % find_version)
        if not find_version:
            return None
        new_url = version_href[find_version]
        print("downloading......\n%s" % new_url)
        ret = self.download_chromadrive(new_url)
        if not ret:
            return None
        self.unzip()
    def start(self):
        '''读取本地chrome version'''
        version = list(filter(None, [self.get_version_via_com(p) for p in self.local_chrome_paths]))[0]
        if not version:
            print("check chrome browser version failed!")
            return None
        print("chrome browser version:", version)
        '''下载网页端与本地匹配的chromedriver.exe'''
        version_href = self.get_chromedriver_urls()
        if not version_href:
            print("request %s failed!"%self.chromedrive_url)
            return None
        if os.path.exists(r"chromedriver_win32\chromedriver-win32\chromedriver.exe"):
            local_version=self.get_chromedriver_version(r"chromedriver_win32\chromedriver-win32\chromedriver.exe")
            if local_version<version.split(".")[0]:
                self.start_(version, version_href)
        else:
            self.start_(version, version_href)



if __name__ == "__main__":
    chrome = auto_download_chromedrive()
    # print(chrome.get_chromedriver_version(r"..\..\chromedriver_win32\chromedriver-win32\chromedriver.exe"))
    chrome.start()




