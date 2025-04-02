# 导入必要的库
import os
import re
import sparkdesk
import _thread as thread
import os
import time
import base64
import datetime
import hashlib
import hmac
import json
from urllib.parse import urlparse
import ssl
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
import websocket

# 定义一个函数来读取每周的 txt 文件

def read_weekly_files(folder_path):
    weekly_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    all_completed_tasks = []
    for file in weekly_files:
        file_path = os.path.join(folder_path, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            completed_tasks = []
            for line in lines:
                if line.strip().startswith('-'):
                    break
                task = line.strip()
                if task:
                    completed_tasks.append(task)
            all_completed_tasks.extend(completed_tasks)
    return all_completed_tasks

# 定义一个函数来按归属分类整理任务

def organize_tasks(tasks):
    task_dict = {}
    for task in tasks:
        match = re.match(r'([^-]+)-(.+)', task)
        if match:
            category = match.group(1).strip()
            task_content = match.group(2).strip()
            if category not in task_dict:
                task_dict[category] = []
            task_dict[category].append(task_content)
    return task_dict

# 定义一个函数来为每个分类下的任务添加序号

def add_task_numbers(task_dict):
    organized_text = ''
    for category, tasks in task_dict.items():
        organized_text += f'{category}（\n'
        for i, task in enumerate(tasks, start=1):
            organized_text += f'  {i}. {task} \n'
        organized_text += '）\n\n'
    return organized_text

# 定义一个函数来将整理好的任务写入月 txt 文件

def write_monthly_file(organized_text, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(organized_text)

# 定义一个函数来生成自评

def generate_self_evaluation(task_dict):
    categories = ', '.join(task_dict.keys())
    all_keywords = set()
    for tasks in task_dict.values():
        for task in tasks:
            # 简单示例：假设关键词用空格分隔
            keywords = task.split()
            all_keywords.update(keywords)
    keyword_summary = ', '.join(all_keywords)
    # 调用讯飞星火 API 生成自评
    # appid、api_key、api_secret 三个服务认证信息请前往开放平台控制台查看（https://console.xfyun.cn/services/bm35）
    appid = "你的appid"
    api_key = "你的apikey"
    api_secret = "你的apikey"
    prompt = f'请根据以下任务分类和关键词总结生成一份200字内的自评：分类：{categories}；关键词总结：{keyword_summary}'
    Spark_url = "wss://spark-api.xf-yun.com/v4.0/chat"  # Max 环境的地址 
    domain = "4.0Ultra"  # Max版本
    class Ws_Param(object):
        # 初始化
        def __init__(self, APPID, APIKey, APISecret, gpt_url):
            self.APPID = APPID
            self.APIKey = APIKey
            self.APISecret = APISecret
            self.host = urlparse(gpt_url).netloc
            self.path = urlparse(gpt_url).path
            self.gpt_url = gpt_url

        # 生成url
        def create_url(self):
            # 生成RFC1123格式的时间戳
            now = datetime.now()
            date = format_date_time(mktime(now.timetuple()))

            # 拼接字符串
            signature_origin = "host: " + self.host + "\n"
            signature_origin += "date: " + date + "\n"
            signature_origin += "GET " + self.path + " HTTP/1.1"

            # 进行hmac-sha256进行加密
            signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                     digestmod=hashlib.sha256).digest()

            signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

            authorization_origin = f'api_key=\"{self.APIKey}\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"{signature_sha_base64}\"'

            authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

            # 将请求的鉴权参数组合为字典
            v = {
                "authorization": authorization,
                "date": date,
                "host": self.host
            }
            # 拼接鉴权参数，生成url
            url = self.gpt_url + '?' + urlencode(v)
            # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
            return url

    # 收到websocket错误的处理
    def on_error(ws, error):
        print("### error:", error)

    # 收到websocket关闭的处理
    def on_close(ws, close_status_code, close_msg):
        print("### closed ###")

    # 收到websocket连接建立的处理
    def on_open(ws):
        thread.start_new_thread(run, (ws,))

    def run(ws, *args):
        data = json.dumps(gen_params(appid=ws.appid, query=ws.query, domain=ws.domain))
        ws.send(data)

    # 收到websocket消息的处理
    def on_message(ws, message):
        # print(message)
        data = json.loads(message)
        code = data['header']['code']
        if code != 0:
            print(f'请求错误: {code}, {data}')
            ws.close()
        else:
            choices = data["payload"]["choices"]
            status = choices["status"]
            content = choices["text"][0]["content"]
            nonlocal evaluation
            evaluation += content
            if status == 2:
                print("#### 关闭会话")
                ws.close()

    def gen_params(appid, query, domain):
        """
        通过appid和用户的提问来生成请参数
        """

        data = {
            "header": {
                "app_id": appid,
                "uid": "1234",           
                # "patch_id": []    #接入微调模型，对应服务发布后的resourceid           
            },
            "parameter": {
                "chat": {
                    "domain": domain,
                    "temperature": 0.5,
                    "max_tokens": 4096,
                    "auditing": "default",
                }
            },
            "payload": {
                "message": {
                    "text": [{"role": "user", "content": query}]
                }
            }
        }
        return data

    evaluation = ''
    wsParam = Ws_Param(appid, api_key, api_secret, Spark_url)
    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()

    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
    ws.appid = appid
    ws.query = prompt
    ws.domain = domain
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    return evaluation

# 定义一个函数来生成新的自评

def generate_new_self_evaluation(task_dict):
    categories = ', '.join(task_dict.keys())
    return f'本月专注于 {categories} 的各项任务，包括需求开发&优化、运维功能、问题排查修复等，整体上进展顺利，内容均已完成。'

# 主函数

def main():
    folder_path = '.'  # 假设每周的 txt 文件都在当前目录下
    output_file = '月.txt'
    # 读取每周的 txt 文件
    all_completed_tasks = read_weekly_files(folder_path)
    # 按归属分类整理任务
    task_dict = organize_tasks(all_completed_tasks)
    # 为每个分类下的任务添加序号
    organized_text = add_task_numbers(task_dict)

    # 生成新的自评
    new_self_evaluation = generate_new_self_evaluation(task_dict)
    # 将新自评添加到整理好的任务和原自评后面
    organized_text += f'\n\n简短自评：\n\n{new_self_evaluation}'
    
    # 生成AI自评
    self_evaluation = generate_self_evaluation(task_dict)
    # 将AI自评添加到整理好的任务后面
    organized_text += f'\n\nAI自评：\n\n{self_evaluation}'
    
    # 将整理好的任务和自评写入月 txt 文件
    write_monthly_file(organized_text, output_file)
    print(f'已将整理好的任务和自评写入 {output_file} 文件。')

if __name__ == '__main__':
    main()