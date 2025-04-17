import os
import json
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)
# 配置 CORS，允许来自所有源的请求
CORS(app)

# 百度地图API的AK（从环境变量获取）
BAIDU_MAP_AK = os.getenv('BAIDU_MAP_AK')
if not BAIDU_MAP_AK:
    print("警告: BAIDU_MAP_AK 环境变量未设置!")

# 加载城市映射数据
def load_city_mapping():
    try:
        city_mapping = []
        with open('cities.jsonl', 'r', encoding='utf-8') as f:
            for line in f:
                city_mapping.append(json.loads(line.strip()))
        return city_mapping
    except Exception as e:
        print(f"加载城市数据失败: {e}")
        return []

CITY_MAPPING = load_city_mapping()
if not CITY_MAPPING:
    print("警告: 城市映射数据为空!")

def get_location_by_ip(ip=None):
    """根据IP获取地理位置信息"""
    # 如果没有提供IP且没有设置默认IP，使用一个已知的公网IP用于测试
    if not ip:
        ip = os.getenv("DEFAULT_IP")
        if not ip:
            print("警告: 未提供IP且DEFAULT_IP环境变量未设置，使用备用IP")
            ip = "220.181.38.148"  # 备用公网IP
    
    print(f"正在使用IP地址: {ip}")
    
    url = "https://api.map.baidu.com/location/ip"
    params = {
        "ip": ip,
        "coor": "bd09ll",
        "ak": BAIDU_MAP_AK,
    }
    
    try:
        response = requests.get(url=url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"百度定位API响应: {data}")
        
        if data.get('status') == 0:
            return data
        else:
            print(f"百度定位API返回错误，状态码: {data.get('status')}, 消息: {data.get('message', '无错误信息')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求定位接口失败: {e}")
        return None

def get_weather(city_code):
    """根据城市代码获取天气信息"""
    url = f"http://t.weather.itboy.net/api/weather/city/{city_code}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求天气接口失败: {e}")
        return None

def find_city_code(city_name, city_mapping):
    """根据城市名称查找城市代码"""
    if not city_name:
        return None
        
    # 去除可能的省市后缀
    normalized_name = city_name.replace("市", "").replace("省", "").strip()
    
    for city in city_mapping:
        # 检查城市名或省份名是否匹配
        city_normalized = city["city"].replace("市", "").replace("省", "").strip()
        province_normalized = city["province"].replace("市", "").replace("省", "").strip()
        
        if (normalized_name == city_normalized or
            normalized_name == province_normalized):
            return city["code"]
    
    return None

@app.route('/')
def index():
    # 返回 HTML 文件
    # return send_from_directory('.', 'weather.html')
    return send_from_directory('.', 'wardrobe.html')

@app.route('/weather', methods=['GET'])
def weather():
    # 获取查询参数
    city_name = request.args.get('city')
    ip = request.args.get('ip')
    
    # 1. 尝试通过城市名获取天气
    if city_name:
        print(f"使用提供的城市名: {city_name}")
        city_code = find_city_code(city_name, CITY_MAPPING)
        if city_code:
            weather_data = get_weather(city_code)
            if weather_data and weather_data.get('status') == 200:
                return process_weather_data(weather_data, city_name)
            else:
                return jsonify({"error": f"获取城市 {city_name} 的天气信息失败"}), 500
        else:
            # 如果找不到城市代码，回退到IP定位
            print(f"找不到城市 {city_name} 的代码，尝试IP定位")
    
    # 2. 尝试通过IP定位城市
    print("尝试通过IP定位城市")
    location_data = get_location_by_ip(ip)
    
    if not location_data:
        # 3. 如果IP定位失败，使用默认城市
        default_city = "北京"
        print(f"IP定位失败，使用默认城市: {default_city}")
        city_code = find_city_code(default_city, CITY_MAPPING)
        if not city_code:
            return jsonify({"error": "无法通过IP定位且默认城市代码获取失败"}), 500
        
        weather_data = get_weather(city_code)
        if not weather_data or weather_data.get('status') != 200:
            return jsonify({"error": "获取默认城市天气信息失败"}), 500
            
        return process_weather_data(weather_data, default_city)
    
    # IP定位成功
    city_name = location_data['content']['address_detail']['city']
    print(f"通过IP定位到城市: {city_name}")
    
    # 查找城市代码
    city_code = find_city_code(city_name, CITY_MAPPING)
    if not city_code:
        return jsonify({"error": f"找不到城市 {city_name} 的代码"}), 404
    
    # 获取天气信息
    weather_data = get_weather(city_code)
    if not weather_data or weather_data.get('status') != 200:
        return jsonify({"error": "获取天气信息失败"}), 500
    
    return process_weather_data(weather_data, city_name)

def process_weather_data(weather_data, city_name):
    """处理天气数据并返回格式化的响应"""
    
    # 提取需要的天气信息
    date = weather_data.get('date')
    data = weather_data.get('data', {})
    current_temp = data.get('wendu')
    humidity = data.get('shidu')
    
    # 获取当日天气预报
    forecast = data.get('forecast', [{}])[0]
    high_temp = forecast.get('high')
    low_temp = forecast.get('low')
    wind_power = forecast.get('fl')
    
    # 构建响应
    response = {
        # "date": date,
        "city": city_name,
        "current_temperature": f"{current_temp}℃",
        "humidity": humidity,
        "today": {
            "high_temperature": "最"+high_temp if high_temp else "未知",
            "low_temperature": "最"+low_temp if low_temp else "未知",
            "wind_power": wind_power
        }
    }
    
    return jsonify(response)

if __name__ == '__main__':
    # 检查环境变量
    if not BAIDU_MAP_AK:
        print("错误: 未设置BAIDU_MAP_AK环境变量，IP定位功能将不可用")
    
    # 检查城市数据
    if not CITY_MAPPING:
        print("错误: 城市映射数据为空，请确保cities.jsonl文件存在且格式正确")
    else:
        print(f"成功加载了 {len(CITY_MAPPING)} 个城市的数据")
        
    app.run(host='0.0.0.0', port=8888, debug=True)