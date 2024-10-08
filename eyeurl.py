import sys
from bs4 import BeautifulSoup
from lib import urlReq
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import lib.downloadDriver as Chrome
from dominate.tags import *
import dominate as dom
import time
import os
import multiprocessing
header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
                        "Connection": "close"
                    }  # header
img_names = []
urlpaste = urlReq.Request()
def func_init(txt_path,que,dir_name):
    exch=[]
    with open(txt_path,'r') as f:
        while True:
            line = f.readline()
            if line:
                url=line.replace('\n','')
                if url not in exch:
                    que.put(url)
                exch.append(url)
            else:
                break
        f.close()
    dir_mk(os.getcwd()+'/result')
    dir_mk(dir_name)
    dir_mk(dir_name +'/data')

def dir_mk(path):
    if os.path.exists(path):
        if not os.path.isdir(path):
            os.mkdir(path)
    else:
        os.mkdir(path)

def reqProcess(urlpaste,que,lock,m_dict,timeout,wait_time,dir_name):
    with lock:
        option = webdriver.ChromeOptions()
        option.add_argument('--window-size=1600,800')  # 设置option
        option.page_load_strategy = 'eager'  # 设置option
        option.add_argument('--headless=old')  # 设置option
        option.add_argument('--disable-gpu')  # 设置option
        option.add_argument('--incognito')  # 设置option
        option.add_argument('--ignore-certificate-errors')  # 设置option
        option.add_experimental_option('excludeSwitches', ['enable-logging'])  # 设置option
        path=r"chromedriver_win32\chromedriver-win32\chromedriver.exe"
        driver = webdriver.Chrome(service=Service(executable_path=path),options=option)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => False}) "})
    while True:
        if not que.empty():
            url = que.get()
            num=que.qsize()+1
            req(urlpaste,url, header, driver, m_dict,timeout,wait_time,num,dir_name)
        else:
            driver.quit()
            break
    

def req(urlpaste,url,header,driver,m_dict,timeout,wait_time,num,dir_name):
    try:
        resp = urlpaste.req_get(url, verify=False, header=header,allow_redirects=False,timeout=timeout)
        if resp.status_code!=200:
            status_code=resp.status_code
            resp = urlpaste.req_get(url, verify=False,header=header,allow_redirects=True,timeout=timeout)
        else:
            status_code=resp.status_code
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, features='xml')
        res_title = soup.find("title")
        driver.get(url)
        time.sleep(wait_time)
        img_path='{0}.png'.format(str(num))
        driver.save_screenshot(dir_name+'/data/'+img_path)
        #m_screenshots.update({img_path: img})
        if res_title:
            print("[+] 已探测url:{0},状态码:{1},站点标题:{2}".format(url,status_code,soup.title.text))
            m_dict.update({url:[resp.status_code, soup.title.text,img_path]})
        else:
            print("[+] 已探测url:{0},状态码:{1},站点标题:{2}".format(url, resp.status_code, '未获取到标题'))
            m_dict.update({url: [resp.status_code,'未获取到标题',img_path]})
    except Exception as e:
        print("[x] 探测url:{0}失败:网站连接超时".format(url))
        m_dict.update({url: ["连接失败",'x_x!','']})

def report(m_dict,now_time):
    with open('result/result_{0}/result_{1}.txt'.format(now_time,now_time),'w',encoding='utf-8') as f:
        for url,[resp_code,resp_title,img_path] in m_dict.items():
            f.write('{0}\t{1}\t{2}\t{3}\n'.format(url,resp_code,resp_title,'data/'+img_path))
        f.close()
    doc = dom.document(title='result_{0}'.format(now_time))
    with doc.head:
        meta(charset='utf-8')
    with doc.add(body()).add(div(id='content',align="center")):
        with table(border='1',align="center").add(tbody()):
            # 生成报表头部
            with tr(align='center'):
                td(colspan="7").add('url探测结果')
            l = tr(align="center", bgcolor="#0080FF", style="color:white")

            l += td('url详情')
            l += td('截图')
            # 插入表格数据
            for url,[resp_code,resp_title,img_path] in m_dict.items():
                l = tr(align='center')
                with l:
                    td(a(url,href=url,target="_blank"),' '+str(resp_code)+' '+resp_title)
                    td(img(src='data/{0}'.format(img_path),style='width:800px;hight:200px'))
    with open('result/result_{0}/result_{1}.html'.format(now_time,now_time),'w',encoding='utf-8') as f:
        f.write(doc.render())
        f.close()

def mainFunc(txt_path,timeout,wait_time,process_rate):
    old_time=time.time()
    print('************url探测开始************')
    process_list=[]
    m=multiprocessing.Manager()
    m_dict=m.dict()
    #m_screenshots=m.dict()
    m_que=m.Queue()
    now_time = str(time.time_ns())
    dir_name = os.getcwd() + '/result/result_' + now_time  # 截图保存的目录
    func_init(txt_path,m_que,dir_name)
    if m_que.qsize()<5:
        process_rate=m_que.qsize()
    lock=m.Lock()
    for i in range(process_rate):
        process=multiprocessing.Process(target=reqProcess,args=(urlpaste,m_que,lock,m_dict,timeout,wait_time,dir_name))
        process_list.append(process)
    for i in process_list:
        i.start()
    for i in process_list:
        i.join()
    print('************url探测结束,请耐心等待报表生成~************\n')
    #for key,value in m_screenshots.items():
    #    with open(dir_name+'/data/'+key, 'wb') as f:
    #        f.write(value)
    #        f.close()
    print("报表生成完毕，报表所在位置:{0}".format(dir_name))
    report(m_dict,now_time)
    new_time=time.time()
    cost_time=new_time-old_time
    print("去重后，url探测共计：{0}个,共耗时{1}秒,感谢使用~".format(len(m_dict),int(cost_time)))

if __name__=='__main__':
    if len(sys.argv)<2:
        print('\n-------------欢迎使用本程序，帮助内容如下:------------\n  作者：云小书 公众号：恒运安全 参数说明:\n')
        print('\t-f\t\t需要探测的url所在的文件')
        print('\t-t\t\t线程数,默认5,建议不要超过10')
        print('\t-delay\t\t网页截图等待时间(s),默认1s,建议不要太大')
        print('\t-timeout\t\t网页连接超时时间(s),默认30s,建议不要太大')
        print('\t挂代理请在cmd内执行(ip、端口自行更改)：set http_proxy=http://127.0.0.1:7890')
        print('\t请注意：本程序自动url去重')
        sys.exit()
    chrome = Chrome.auto_download_chromedrive()
    chrome.start()
    import argparse
    parser=argparse.ArgumentParser(description='eyeurl')
    parser.add_help=True
    parser.add_argument('-f',type=str,required=True,help='需要探测的url所在的文件')
    parser.add_argument('-t',type=int,default=5,help='线程数,默认5,建议不要超过10')
    parser.add_argument('-delay',type=int,default=1,help='网页截图等待时间(s),默认1s,建议不要太大')
    parser.add_argument('-timeout',type=int,default=30,help='网页连接超时时间(s),默认30s,建议不要太大')
    args=parser.parse_args()
    txt_path=args.f
    process_rate=args.t
    timeout=args.timeout
    wait_time=args.delay
    mainFunc(txt_path,timeout,wait_time,process_rate)
