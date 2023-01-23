import requests as rq
from requests.packages import urllib3

class Request:
    def __init__(self):
        urllib3.disable_warnings()
        self.s=rq.Session()
    def req_get(self,url,header='',allow_redirects=True,verify=False,timeout=3):
        resp=self.s.get(url,headers=header,verify=verify, timeout=timeout,allow_redirects=allow_redirects)
        self.s.close()
        return resp
    def req_post(self,url,header='',data='',allow_redirects=True,verify=False,timeout=3):
        resp = self.s.post(url, headers=header,data=data,verify=verify, timeout=timeout,allow_redirects=allow_redirects)
        self.s.close()
        return resp


# from webHack import urlReq
# import time
# if __name__ == '__main__':
#     # url='https://sts.didiglobal.com/sg1/api/free/signal-upm-service/pc_login'
#     url='https://epassport.diditaxi.com.cn'
#     header={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36","Connection":"close"}
#     urlpaste= urlReq.Request()
#     with open('C:\\Users\\93243\\Desktop\\url.txt','r') as f:
#         while True:
#             line = f.readline()
#             if line:
#                 line=line.replace('\n','')
#                 resp=urlpaste.req_post(url+line,header)
#                 print("{0}\t{1}".format(url,resp.text))
#                 time.sleep(1.5)
#             else:
#                 break
#         f.close()