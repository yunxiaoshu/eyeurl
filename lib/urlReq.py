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
