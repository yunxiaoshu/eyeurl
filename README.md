## eyeurl使用说明

### 开发说明

[eyeurl](https://github.com/yunxiaoshu/eyeurl)由作者：云小书 开发，源于日常渗透测试中，信息收集到的url过多，挨个打开查看比较繁琐，且效率极低，网上有大佬开发的[eyewitness](https://github.com/FortyNorthSecurity/EyeWitness/)，且ui布局各方面都比较完善，大家可以使用大佬开发的工具。

而为什么有[eyewitness](https://github.com/FortyNorthSecurity/EyeWitness/)的前提下，还自己开发一个[eyeurl](https://github.com/yunxiaoshu/eyeurl)呢？

本人在使用[eyewitness](https://github.com/FortyNorthSecurity/EyeWitness/)时感觉不是很称手，大家若是介意duck不必使用[eyeurl](https://github.com/yunxiaoshu/eyeurl)

### 使用说明

1. python环境需满足python3
2. 需在电脑中安装谷歌浏览器
3. 下载好后执行pip install  -r requirements

上述三点准备就绪后，执行下方命令可查看说明

```shell
python eyeurl.py -h
```

![image-20230121161808270](https://testingcf.jsdelivr.net/gh/yunxiaoshu/images/image-20230121161808270.png)

### 示例

```
python eyeurl.py -f C:\test.txt -t 20
```

![image-20230121162147598](https://testingcf.jsdelivr.net/gh/yunxiaoshu/images/image-20230121162147598.png)

![image-20230121162449561](https://testingcf.jsdelivr.net/gh/yunxiaoshu/images/image-20230121162449561.png)

若出现如下图第一个链接的标题与截图内容对应不起来，你应该清理一下你的浏览器缓存再重新运行[eyeurl](https://github.com/yunxiaoshu/eyeurl)

![image-20230121162813727](https://testingcf.jsdelivr.net/gh/yunxiaoshu/images/image-20230121162813727.png)

话还是之前那句，大家若是介意duck不必使用[eyeurl](https://github.com/yunxiaoshu/eyeurl)

推荐大佬开发的[eyewitness](https://github.com/FortyNorthSecurity/EyeWitness/)，大家在使用过程中遇到什么问题或者有什么建议的，欢迎大家提issues

最后，非常感谢[eyewitness](https://github.com/FortyNorthSecurity/EyeWitness/)提供的思路，祝23年大家新年快乐~