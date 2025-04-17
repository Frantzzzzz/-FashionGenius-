from flask import Flask, request, jsonify, render_template
import requests
import time
import os
from dotenv import load_dotenv

# 加载环境变量（APIkey）
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

# 新增的URL上传接口
@app.route('/api/upload/url', methods=['POST'])
def upload_url():
    data = request.json
    image_url = data.get('url', '').strip()
    image_type = data.get('type', 'unknown')
    
    # 简单验证URL格式
    if not image_url.startswith(('http://', 'https://')):
        return jsonify({'error': '请输入有效的HTTP/HTTPS链接'}), 400
    
    # 验证图片URL是否有效
    try:
        response = requests.head(image_url, timeout=5)
        if response.status_code != 200:
            return jsonify({'error': '图片URL不可访问'}), 400
        
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            return jsonify({'error': 'URL不是有效的图片'}), 400
    except Exception as e:
        return jsonify({'error': f'验证图片URL失败: {str(e)}'}), 400
    
    return jsonify({
        'url': image_url,
        'type': image_type
    })

# 虚拟试衣模型函数：开始试衣任务
def clothes_tryon(model_image_url, top_garment_url, bottom_garment_url):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis"
    
    payload = {
        "model": "aitryon",  # 虚拟试衣模型名称
        "input": {
            "top_garment_url": top_garment_url,
            "bottom_garment_url": bottom_garment_url,
            "person_image_url": model_image_url
        },
        "parameters": {
            "resolution": -1,  # 输出图片分辨率，-1表示原图分辨率
            "restore_face": True  # 是否保留人脸
        }
    }
    
    headers = {
        "X-DashScope-Async": "enable",  # 异步模式
        "Authorization": "Bearer " + os.getenv("API_KEY"),  # 使用环境变量中的 API 密钥
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    result = response.json()
    
    print(f"Response status code: {response.status_code}")
    print(f"Response result: {result}")
    
    if response.status_code == 200 and result.get("output", {}).get("task_status") == "PENDING":
        task_id = result['output']['task_id']
        print(f"任务创建成功，任务ID：{task_id}")
        return task_id
    else:
        print("请求失败或未返回任务ID")
        return None


# 查询异步执行的作业结果，并设置最大重试次数防止无限等待
def query_task_result(task_id, max_retries=10):
    url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    headers = {
        "Authorization": "Bearer " + os.getenv("API_KEY")
    }

    retries = 0
    while retries < max_retries:
        response = requests.get(url, headers=headers)
        result = response.json()
        
        print(f"Query task status response: {response.status_code}")
        print(f"Task status response: {result}")
        
        task_status = result.get("output", {}).get("task_status")
        
        if task_status == "SUCCEEDED":
            image_url = result["output"]["image_url"]
            print(f"生成的合成图像链接：{image_url}")
            return {"status": "success", "image_url": image_url}
        elif task_status == "PENDING" or task_status == "RUNNING":
            print(f"任务正在处理中（状态：{task_status}），请稍候...")
            time.sleep(30)  # 每30秒钟轮询一次状态
            retries += 1
        else:
            print(f"任务失败或出错，错误信息：{result}")
            return {"status": "failed", "error": result}
    
    print("任务处理超时，未能获取合成图像")
    return {"status": "timeout", "error": "任务超时"}

# POST 提交试衣任务 → 返回 task_id
@app.route('/api/tryon', methods=['POST'])
def tryon():
    data = request.get_json()
    model_image_url = data['model_image_url']
    top_garment_url = data['top_garment_url']
    bottom_garment_url = data['bottom_garment_url']
    
    # 调用虚拟试衣模型函数，创建试衣任务
    task_id = clothes_tryon(model_image_url, top_garment_url, bottom_garment_url)
    
    if task_id:
        return jsonify({'task_id': task_id}), 200
    else:
        return jsonify({'error': '任务创建失败'}), 500

# GET 查询结果 → 返回 image_url
@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task_result = query_task_result(task_id)
    if task_result['status'] == 'success':
        return jsonify({'image_url': task_result['image_url']}), 200
    else:
        return jsonify({'error': task_result.get('error', '查询失败')}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5004)
